import os
import re

ecr_steps_template = '''      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-south-1
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2
'''

workflows_dir = 'd:/Resource Coordination Platform/.github/workflows'

services = {
    'ci-analytics.yml': ('analytics', 'services/analytics/Dockerfile', '.'),
    'ci-gateway.yml': ('gateway', 'gateway/Dockerfile', '.'),
    'ci-iam.yml': ('iam', 'services/iam/Dockerfile', '.'),
    'ci-logistics.yml': ('logistics', 'services/logistics/Dockerfile', '.'),
    'ci-rto.yml': ('rto', '', 'services/rto') 
}

for filename, (svc_name, dockerfile_path, build_context) in services.items():
    filepath = os.path.join(workflows_dir, filename)
    with open(filepath, 'r') as f:
        content = f.read()

    # Find "build:" and then the checkout step within it
    build_idx = content.find('  build:')
    if build_idx == -1:
        continue
    
    checkout_marker = '- uses: actions/checkout@v4'
    checkout_idx = content.find(checkout_marker, build_idx)
    if checkout_idx == -1:
        continue

    # Slice everything up to checkout
    new_content = content[:checkout_idx + len(checkout_marker)] + '\n'
    new_content += ecr_steps_template

    if dockerfile_path:
        new_content += f'      - run: docker build -f {dockerfile_path} -t ${{{{ steps.login-ecr.outputs.registry }}}}/rcp/{svc_name}:latest {build_context}\n'
    else:
        new_content += f'      - run: docker build -t ${{{{ steps.login-ecr.outputs.registry }}}}/rcp/{svc_name}:latest {build_context}\n'

    new_content += f'      - run: docker push ${{{{ steps.login-ecr.outputs.registry }}}}/rcp/{svc_name}:latest\n'

    with open(filepath, 'w') as f:
        f.write(new_content)
    print(f'Updated {filename}')
