# BLU Suite - AWS Deployment Guide

## Prerequisites

### AWS Account Setup
- AWS Account with appropriate permissions
- AWS CLI installed and configured
- EC2 key pair created
- Domain name (optional but recommended)

### Local Requirements
- Python 3.13.3
- Git
- PostgreSQL client tools

## AWS Services Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Route 53 (DNS)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   CloudFront (CDN)                           │
│              (Static Files & Media)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Application Load Balancer (ALB)                 │
└────────┬───────────────────────────────────────┬────────────┘
         │                                       │
┌────────▼────────┐                    ┌────────▼────────┐
│   EC2 Instance  │                    │   EC2 Instance  │
│   (App Server)  │                    │   (App Server)  │
│   - Gunicorn    │                    │   - Gunicorn    │
│   - Nginx       │                    │   - Nginx       │
└────────┬────────┘                    └────────┬────────┘
         │                                       │
         └───────────────┬───────────────────────┘
                         │
         ┌───────────────▼───────────────┐
         │    RDS PostgreSQL Database    │
         │    (Multi-AZ for HA)          │
         └───────────────┬───────────────┘
                         │
         ┌───────────────▼───────────────┐
         │         S3 Buckets            │
         │  - Media Files                │
         │  - Static Files               │
         │  - Backups                    │
         └───────────────────────────────┘
```

## Step 1: Database Setup (RDS PostgreSQL)

### Create RDS Instance
```bash
aws rds create-db-instance \
    --db-instance-identifier blusuite-prod-db \
    --db-instance-class db.t3.medium \
    --engine postgres \
    --engine-version 15.4 \
    --master-username blusuite_admin \
    --master-user-password <SECURE_PASSWORD> \
    --allocated-storage 100 \
    --storage-type gp3 \
    --storage-encrypted \
    --backup-retention-period 30 \
    --multi-az \
    --vpc-security-group-ids sg-xxxxxxxxx \
    --db-subnet-group-name blusuite-db-subnet \
    --publicly-accessible false
```

### Database Configuration
- **Instance Type**: db.t3.medium (2 vCPU, 4GB RAM) - Start small, scale as needed
- **Storage**: 100GB GP3 (scalable)
- **Multi-AZ**: Yes (for high availability)
- **Backup**: 30 days retention
- **Encryption**: Enabled

### Security Group Rules
- **Inbound**: PostgreSQL (5432) from application security group only
- **Outbound**: All traffic

## Step 2: S3 Buckets Setup

### Create S3 Buckets
```bash
# Media files bucket
aws s3 mb s3://blusuite-prod-media --region us-east-1

# Static files bucket
aws s3 mb s3://blusuite-prod-static --region us-east-1

# Backups bucket
aws s3 mb s3://blusuite-prod-backups --region us-east-1
```

### Configure Bucket Policies
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::blusuite-prod-static/*"
        }
    ]
}
```

### Enable CORS (for media bucket)
```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "HEAD", "PUT", "POST"],
        "AllowedOrigins": ["https://yourdomain.com"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000
    }
]
```

### Enable Versioning (for backups)
```bash
aws s3api put-bucket-versioning \
    --bucket blusuite-prod-backups \
    --versioning-configuration Status=Enabled
```

## Step 3: EC2 Instance Setup

### Launch EC2 Instance
```bash
aws ec2 run-instances \
    --image-id ami-xxxxxxxxx \
    --instance-type t3.medium \
    --key-name blusuite-prod-key \
    --security-group-ids sg-xxxxxxxxx \
    --subnet-id subnet-xxxxxxxxx \
    --iam-instance-profile Name=BLUSuiteEC2Role \
    --user-data file://user-data.sh \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=BLUSuite-Prod-App}]'
```

### Instance Configuration
- **Instance Type**: t3.medium (2 vCPU, 4GB RAM)
- **OS**: Ubuntu 22.04 LTS
- **Storage**: 50GB GP3
- **Auto Scaling**: Configure based on CPU/Memory metrics

### Security Group Rules
- **Inbound**:
  - SSH (22) from your IP only
  - HTTP (80) from ALB security group
  - HTTPS (443) from ALB security group
- **Outbound**: All traffic

### IAM Role Permissions
Create IAM role `BLUSuiteEC2Role` with policies:
- AmazonS3FullAccess (or custom policy for specific buckets)
- CloudWatchAgentServerPolicy
- AmazonSSMManagedInstanceCore (for Systems Manager)

## Step 4: Application Deployment

### User Data Script (user-data.sh)
```bash
#!/bin/bash
set -e

# Update system
apt-get update
apt-get upgrade -y

# Install dependencies
apt-get install -y python3.13 python3.13-venv python3-pip nginx postgresql-client git supervisor

# Create application user
useradd -m -s /bin/bash blusuite
mkdir -p /home/blusuite/app
chown -R blusuite:blusuite /home/blusuite

# Clone repository (use deployment key)
cd /home/blusuite
sudo -u blusuite git clone https://github.com/yourorg/BLU_suite.git app

# Setup virtual environment
cd /home/blusuite/app
sudo -u blusuite python3.13 -m venv venv
sudo -u blusuite venv/bin/pip install --upgrade pip
sudo -u blusuite venv/bin/pip install -r requirements.txt
sudo -u blusuite venv/bin/pip install gunicorn psycopg2-binary boto3

# Create .env file (populate from AWS Secrets Manager)
cat > /home/blusuite/app/.env << 'EOF'
DEBUG=False
SECRET_KEY=<FETCH_FROM_SECRETS_MANAGER>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/blusuite
AWS_ACCESS_KEY_ID=<IAM_ROLE_HANDLES_THIS>
AWS_SECRET_ACCESS_KEY=<IAM_ROLE_HANDLES_THIS>
AWS_STORAGE_BUCKET_NAME=blusuite-prod-media
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=blusuite-prod-static.s3.amazonaws.com
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<SES_SMTP_USER>
EMAIL_HOST_PASSWORD=<SES_SMTP_PASSWORD>
EOF
chown blusuite:blusuite /home/blusuite/app/.env
chmod 600 /home/blusuite/app/.env

# Run migrations
cd /home/blusuite/app
sudo -u blusuite venv/bin/python manage.py migrate
sudo -u blusuite venv/bin/python manage.py collectstatic --noinput

# Configure Gunicorn
cat > /etc/supervisor/conf.d/blusuite.conf << 'EOF'
[program:blusuite]
command=/home/blusuite/app/venv/bin/gunicorn blu_staff.wsgi:application --bind 127.0.0.1:8000 --workers 4 --timeout 120
directory=/home/blusuite/app
user=blusuite
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/blusuite/gunicorn.log
EOF

# Create log directory
mkdir -p /var/log/blusuite
chown blusuite:blusuite /var/log/blusuite

# Configure Nginx
cat > /etc/nginx/sites-available/blusuite << 'EOF'
upstream blusuite_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    client_max_body_size 50M;
    
    location /static/ {
        alias /home/blusuite/app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        # Redirect to S3
        return 301 https://blusuite-prod-media.s3.amazonaws.com$request_uri;
    }
    
    location / {
        proxy_pass http://blusuite_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
EOF

ln -s /etc/nginx/sites-available/blusuite /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# Start application
supervisorctl reread
supervisorctl update
supervisorctl start blusuite

# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i amazon-cloudwatch-agent.deb
```

## Step 5: Load Balancer Setup

### Create Application Load Balancer
```bash
aws elbv2 create-load-balancer \
    --name blusuite-prod-alb \
    --subnets subnet-xxxxxxxx subnet-yyyyyyyy \
    --security-groups sg-xxxxxxxxx \
    --scheme internet-facing \
    --type application \
    --ip-address-type ipv4
```

### Create Target Group
```bash
aws elbv2 create-target-group \
    --name blusuite-prod-targets \
    --protocol HTTP \
    --port 80 \
    --vpc-id vpc-xxxxxxxxx \
    --health-check-path /health/ \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3
```

### Register Targets
```bash
aws elbv2 register-targets \
    --target-group-arn <TARGET_GROUP_ARN> \
    --targets Id=i-xxxxxxxxx
```

### Create Listener (HTTP)
```bash
aws elbv2 create-listener \
    --load-balancer-arn <ALB_ARN> \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=<TARGET_GROUP_ARN>
```

### Create Listener (HTTPS) - After SSL Certificate
```bash
aws elbv2 create-listener \
    --load-balancer-arn <ALB_ARN> \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=<ACM_CERTIFICATE_ARN> \
    --default-actions Type=forward,TargetGroupArn=<TARGET_GROUP_ARN>
```

## Step 6: SSL Certificate (ACM)

### Request Certificate
```bash
aws acm request-certificate \
    --domain-name yourdomain.com \
    --subject-alternative-names www.yourdomain.com \
    --validation-method DNS \
    --region us-east-1
```

### Validate Certificate
- Add CNAME records to your DNS (Route 53 or external)
- Wait for validation (usually 5-30 minutes)

## Step 7: CloudFront CDN (Optional but Recommended)

### Create CloudFront Distribution
```bash
aws cloudfront create-distribution \
    --origin-domain-name blusuite-prod-alb-xxxxxxxxx.us-east-1.elb.amazonaws.com \
    --default-root-object index.html
```

### Configure Origins
- **Origin 1**: ALB (for dynamic content)
- **Origin 2**: S3 static bucket (for static files)
- **Origin 3**: S3 media bucket (for media files)

### Cache Behaviors
- `/static/*` → S3 static bucket (cache everything)
- `/media/*` → S3 media bucket (cache everything)
- `/*` → ALB (cache based on headers)

## Step 8: Route 53 DNS

### Create Hosted Zone
```bash
aws route53 create-hosted-zone \
    --name yourdomain.com \
    --caller-reference $(date +%s)
```

### Create A Record (Alias to ALB)
```json
{
    "Changes": [{
        "Action": "CREATE",
        "ResourceRecordSet": {
            "Name": "yourdomain.com",
            "Type": "A",
            "AliasTarget": {
                "HostedZoneId": "<ALB_HOSTED_ZONE_ID>",
                "DNSName": "blusuite-prod-alb-xxxxxxxxx.us-east-1.elb.amazonaws.com",
                "EvaluateTargetHealth": true
            }
        }
    }]
}
```

## Step 9: Monitoring & Logging

### CloudWatch Alarms
```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
    --alarm-name blusuite-high-cpu \
    --alarm-description "Alert when CPU exceeds 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/EC2 \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2

# Database connections alarm
aws cloudwatch put-metric-alarm \
    --alarm-name blusuite-db-connections \
    --alarm-description "Alert when DB connections exceed 80" \
    --metric-name DatabaseConnections \
    --namespace AWS/RDS \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2
```

### Application Logs
- **Location**: `/var/log/blusuite/`
- **CloudWatch Logs**: Configure agent to stream logs
- **Retention**: 30 days

## Step 10: Backup Strategy

### RDS Automated Backups
- Enabled by default (30 days retention)
- Daily snapshots during maintenance window

### Manual Snapshots
```bash
aws rds create-db-snapshot \
    --db-instance-identifier blusuite-prod-db \
    --db-snapshot-identifier blusuite-manual-$(date +%Y%m%d)
```

### S3 Backup Script
```bash
#!/bin/bash
# Backup media files to backup bucket
aws s3 sync s3://blusuite-prod-media s3://blusuite-prod-backups/media/$(date +%Y%m%d)/
```

## Step 11: Auto Scaling (Optional)

### Create Launch Template
```bash
aws ec2 create-launch-template \
    --launch-template-name blusuite-prod-template \
    --version-description "BLU Suite production template" \
    --launch-template-data file://launch-template.json
```

### Create Auto Scaling Group
```bash
aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name blusuite-prod-asg \
    --launch-template LaunchTemplateName=blusuite-prod-template \
    --min-size 2 \
    --max-size 6 \
    --desired-capacity 2 \
    --target-group-arns <TARGET_GROUP_ARN> \
    --health-check-type ELB \
    --health-check-grace-period 300 \
    --vpc-zone-identifier "subnet-xxxxxxxx,subnet-yyyyyyyy"
```

### Scaling Policies
```bash
# Scale up policy
aws autoscaling put-scaling-policy \
    --auto-scaling-group-name blusuite-prod-asg \
    --policy-name scale-up \
    --scaling-adjustment 1 \
    --adjustment-type ChangeInCapacity \
    --cooldown 300

# Scale down policy
aws autoscaling put-scaling-policy \
    --auto-scaling-group-name blusuite-prod-asg \
    --policy-name scale-down \
    --scaling-adjustment -1 \
    --adjustment-type ChangeInCapacity \
    --cooldown 300
```

## Environment Variables (.env)

```bash
# Django Settings
DEBUG=False
SECRET_KEY=<GENERATE_STRONG_SECRET_KEY>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,*.elb.amazonaws.com

# Database
DATABASE_URL=postgresql://blusuite_admin:<PASSWORD>@blusuite-prod-db.xxxxxxxxx.us-east-1.rds.amazonaws.com:5432/blusuite

# AWS S3
AWS_ACCESS_KEY_ID=<LEAVE_EMPTY_IF_USING_IAM_ROLE>
AWS_SECRET_ACCESS_KEY=<LEAVE_EMPTY_IF_USING_IAM_ROLE>
AWS_STORAGE_BUCKET_NAME=blusuite-prod-media
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=blusuite-prod-static.s3.amazonaws.com
USE_S3=True

# Email (SES)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<SES_SMTP_USERNAME>
EMAIL_HOST_PASSWORD=<SES_SMTP_PASSWORD>
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS=DENY

# Logging
LOG_LEVEL=INFO
```

## Cost Estimation (Monthly)

### Basic Setup (Single Instance)
- EC2 t3.medium: ~$30
- RDS db.t3.medium (Multi-AZ): ~$120
- S3 Storage (100GB): ~$2.30
- Data Transfer: ~$10-50
- ALB: ~$20
- Route 53: ~$0.50
- **Total**: ~$180-220/month

### Production Setup (Auto Scaling)
- EC2 t3.medium x2-6: ~$60-180
- RDS db.t3.large (Multi-AZ): ~$240
- S3 Storage (500GB): ~$11.50
- Data Transfer: ~$50-200
- ALB: ~$20
- CloudFront: ~$50-100
- Route 53: ~$0.50
- CloudWatch: ~$10
- **Total**: ~$440-800/month

## Post-Deployment Checklist

- [ ] Database migrations completed
- [ ] Static files collected and uploaded to S3
- [ ] SSL certificate validated and installed
- [ ] DNS records configured
- [ ] Health checks passing
- [ ] CloudWatch alarms configured
- [ ] Backup strategy tested
- [ ] Security groups reviewed
- [ ] IAM roles and policies verified
- [ ] Application logs streaming to CloudWatch
- [ ] Load testing completed
- [ ] Monitoring dashboard created
- [ ] Documentation updated
- [ ] Team trained on deployment process

## Maintenance Commands

### Deploy New Version
```bash
# SSH to EC2 instance
ssh -i blusuite-prod-key.pem ubuntu@<EC2_IP>

# Switch to app user
sudo su - blusuite

# Pull latest code
cd /home/blusuite/app
git pull origin main

# Install dependencies
venv/bin/pip install -r requirements.txt

# Run migrations
venv/bin/python manage.py migrate

# Collect static files
venv/bin/python manage.py collectstatic --noinput

# Restart application
sudo supervisorctl restart blusuite
```

### View Logs
```bash
# Application logs
tail -f /var/log/blusuite/gunicorn.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# System logs
journalctl -u nginx -f
```

### Database Backup
```bash
# Create manual snapshot
aws rds create-db-snapshot \
    --db-instance-identifier blusuite-prod-db \
    --db-snapshot-identifier blusuite-backup-$(date +%Y%m%d-%H%M%S)
```

## Troubleshooting

### Application Not Starting
1. Check Gunicorn logs: `tail -f /var/log/blusuite/gunicorn.log`
2. Verify .env file: `cat /home/blusuite/app/.env`
3. Check database connectivity: `psql -h <RDS_ENDPOINT> -U blusuite_admin -d blusuite`
4. Verify migrations: `python manage.py showmigrations`

### High CPU Usage
1. Check CloudWatch metrics
2. Review slow queries in RDS
3. Enable Django Debug Toolbar (staging only)
4. Consider scaling up instance type

### Database Connection Issues
1. Verify security group rules
2. Check RDS instance status
3. Review connection pool settings
4. Monitor active connections

## Security Best Practices

1. **Never commit .env files to Git**
2. **Use AWS Secrets Manager for sensitive data**
3. **Enable MFA for AWS root account**
4. **Regularly update dependencies**
5. **Enable AWS GuardDuty for threat detection**
6. **Use VPC endpoints for S3 access**
7. **Enable CloudTrail for audit logging**
8. **Implement WAF rules on ALB**
9. **Regular security audits**
10. **Backup encryption enabled**

---

**Last Updated**: February 14, 2026
**Version**: 1.0
**Maintained By**: BLU Suite DevOps Team
