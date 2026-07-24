// Package auth verifies IAM-issued RS256 JWTs using the cached JWKS.
// RTO never queries schema_iam: verification is purely cryptographic.
package auth

import (
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"net/http"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

const (
	jwksTTL            = 10 * time.Minute
	minRefreshInterval = 5 * time.Second // rate-limit refresh-on-unknown-kid
)

//struct of the token
type Claims struct {
	UserID   uuid.UUID
	TenantID uuid.UUID
	Roles    []string
	JTI      string
	Expires  time.Time
}

type Verifier struct {
	jwksURL  string
	issuer   string
	audience string

	mu        sync.Mutex
	keys      map[string]*rsa.PublicKey
	fetchedAt time.Time

	denyMu   sync.RWMutex
	denyUser map[uuid.UUID]time.Time // user id -> deny until
	denyJTI  map[string]time.Time    // token id -> deny until
}

func NewVerifier(jwksURL, issuer, audience string) *Verifier {
	return &Verifier{
		jwksURL:  jwksURL,
		issuer:   issuer,
		audience: audience,
		keys:     map[string]*rsa.PublicKey{},
		denyUser: map[uuid.UUID]time.Time{},
		denyJTI:  map[string]time.Time{},
	}
}

type jwk struct {
	Kid string `json:"kid"`
	Kty string `json:"kty"`
	N   string `json:"n"`
	E   string `json:"e"`
}

func parseRSA(k jwk) (*rsa.PublicKey, error) {
	nb, err := base64.RawURLEncoding.DecodeString(k.N)
	if err != nil {
		return nil, err
	}
	eb, err := base64.RawURLEncoding.DecodeString(k.E)
	if err != nil {
		return nil, err
	}
	e := 0
	for _, b := range eb {
		e = e<<8 | int(b)
	}
	return &rsa.PublicKey{N: new(big.Int).SetBytes(nb), E: e}, nil
}

// refreshLocked fetches the JWKS; caller must hold v.mu.
func (v *Verifier) refreshLocked() error {
	resp, err := http.Get(v.jwksURL)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("jwks endpoint returned %d", resp.StatusCode)
	}
	var doc struct {
		Keys []jwk `json:"keys"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&doc); err != nil {
		return err
	}
	keys := map[string]*rsa.PublicKey{}
	for _, k := range doc.Keys {
		if k.Kty != "RSA" {
			continue
		}
		pub, err := parseRSA(k)
		if err != nil {
			continue
		}
		keys[k.Kid] = pub
	}
	v.keys = keys
	v.fetchedAt = time.Now()
	return nil
}

func (v *Verifier) key(kid string) (*rsa.PublicKey, error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	stale := time.Since(v.fetchedAt) > jwksTTL
	_, known := v.keys[kid]
	if (stale || !known) && time.Since(v.fetchedAt) > minRefreshInterval {
		if err := v.refreshLocked(); err != nil && len(v.keys) == 0 {
			return nil, err
		}
	}
	if pub, ok := v.keys[kid]; ok {
		return pub, nil
	}
	return nil, errors.New("unknown signing key")
}

// Warm pre-fetches the JWKS so the first connection doesn't pay the cost.
func (v *Verifier) Warm() error {
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.refreshLocked()
}

func (v *Verifier) Verify(tokenString string) (*Claims, error) {
	token, err := jwt.Parse(
		tokenString,
		func(t *jwt.Token) (interface{}, error) {
			kid, _ := t.Header["kid"].(string)
			return v.key(kid)
		},
		jwt.WithValidMethods([]string{"RS256"}), // algorithm allow-list
		jwt.WithIssuer(v.issuer),
		jwt.WithAudience(v.audience),
		jwt.WithLeeway(60*time.Second),
	)
	if err != nil || !token.Valid {
		return nil, fmt.Errorf("invalid token: %w", err)
	}
	mc, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return nil, errors.New("unexpected claims type")
	}

	sub, _ := mc["sub"].(string)
	tenant, _ := mc["tenant_id"].(string)
	userID, err := uuid.Parse(sub)
	if err != nil {
		return nil, errors.New("invalid sub claim")
	}
	// tenantID, err := uuid.Parse(tenant)
	// if err != nil {
	// 	return nil, errors.New("invalid tenant_id claim")
	// }
	
	var tenantID uuid.UUID
	if tenant != "" {
		tenantID, err = uuid.Parse(tenant)
		if err != nil {
			return nil, errors.New("invalid tenant_id claim")
		}
	} else {
		// Global Users (Volunteers) ලා සඳහා හිස් UUID එකක් පාවිච්චි කරනවා
		tenantID = uuid.Nil 
	}



	claims := &Claims{UserID: userID, TenantID: tenantID}
	if jti, ok := mc["jti"].(string); ok {
		claims.JTI = jti
	}
	if exp, err := mc.GetExpirationTime(); err == nil && exp != nil {
		claims.Expires = exp.Time
	}
	if rawRoles, ok := mc["roles"].([]interface{}); ok {
		for _, r := range rawRoles {
			if s, ok := r.(string); ok {
				claims.Roles = append(claims.Roles, s)
			}
		}
	}

	if v.isDenied(claims) {
		return nil, errors.New("token revoked")
	}
	return claims, nil
}

// DenyUser blocks a user's tokens until `until` (driven by
// iam.user.deactivated / iam.token.revoked events — no hot-path I/O).
func (v *Verifier) DenyUser(userID uuid.UUID, until time.Time) {
	v.denyMu.Lock()
	defer v.denyMu.Unlock()
	v.denyUser[userID] = until
}

func (v *Verifier) DenyJTI(jti string, until time.Time) {
	v.denyMu.Lock()
	defer v.denyMu.Unlock()
	v.denyJTI[jti] = until
}

func (v *Verifier) isDenied(c *Claims) bool {
	v.denyMu.RLock()
	defer v.denyMu.RUnlock()
	now := time.Now()
	if until, ok := v.denyUser[c.UserID]; ok && now.Before(until) {
		return true
	}
	if until, ok := v.denyJTI[c.JTI]; ok && now.Before(until) {
		return true
	}
	return false
}
