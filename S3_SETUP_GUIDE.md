# S3 Storage Setup Guide

## Overview
Your Midjourney Profile Tester now supports **persistent storage** via AWS S3, solving the ephemeral filesystem issue on Streamlit Cloud.

## How It Works

The app now has a **storage abstraction layer** that automatically switches between:
- **Local filesystem** (for development) - default
- **AWS S3** (for production/Streamlit Cloud)

All file operations (images, JSON files) go through this layer, making them persistent across Streamlit Cloud restarts.

## Setup Steps

### 1. Create an S3 Bucket

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
2. Click "Create bucket"
3. Choose a name (e.g., `midjourney-profile-tester`)
4. Select your region (e.g., `us-east-1`)
5. **Block Public Access**: Keep all public access blocked (recommended)
6. Click "Create bucket"

### 2. Create IAM User with S3 Access

1. Go to [IAM Console](https://console.aws.amazon.com/iam/)
2. Click "Users" → "Add users"
3. User name: `midjourney-app`
4. Access type: **Programmatic access** (access key)
5. Attach policy: **AmazonS3FullAccess** (or create custom policy below)
6. Create user and **save the Access Key ID and Secret Access Key**

#### Custom Policy (Recommended - More Secure)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::YOUR-BUCKET-NAME",
                "arn:aws:s3:::YOUR-BUCKET-NAME/*"
            ]
        }
    ]
}
```

### 3. Configure Streamlit Cloud

1. Go to your [Streamlit Cloud](https://share.streamlit.io/) app settings
2. Click "Advanced settings" → "Secrets"
3. Add these secrets:

```toml
# OpenAI
OPENAI_API_KEY = "your-openai-key"

# Storage - Enable S3
USE_S3 = "true"

# AWS S3 Configuration
S3_BUCKET_NAME = "your-bucket-name"
S3_PREFIX = "midjourney-profiles"
AWS_ACCESS_KEY_ID = "your-access-key-id"
AWS_SECRET_ACCESS_KEY = "your-secret-access-key"
AWS_REGION = "us-east-1"
```

4. Save and your app will restart with S3 storage enabled!

### 4. Local Development

For local development, keep `USE_S3=false` in your `.env` file (default):

```bash
# .env file
USE_S3=false
```

This keeps your local testing fast and simple.

## Cost Estimation

AWS S3 is very cheap for this use case:
- **Storage**: ~$0.023/GB/month
- **Requests**: $0.005 per 1,000 PUT/GET requests
- **Estimated monthly cost**: $0.50 - $2.00 for typical usage

## Files Modified

- ✅ `storage.py` - New storage abstraction layer (S3 + local)
- ✅ `storage_helpers.py` - Path-like wrappers for backward compatibility
- ✅ `config.py` - Updated to use storage layer
- ✅ `test_prompts_manager.py` - Updated to use storage layer
- ✅ `midjourney_profile_tester.py` - Updated all file operations
- ✅ `requirements.txt` - Added boto3
- ✅ `.env` - Added S3 configuration (template)

## Testing

### Test Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (uses local filesystem)
streamlit run midjourney_profile_tester.py
```

### Test S3 Connection
```bash
# Set USE_S3=true in .env temporarily
# Add your AWS credentials to .env
# Run the app and upload a test image
# Check AWS S3 console to verify file was uploaded
```

## Troubleshooting

### "NoSuchBucket" Error
- Check bucket name is correct in secrets
- Verify bucket exists in the AWS region you specified

### "Access Denied" Error
- Check IAM user has correct permissions
- Verify AWS credentials are correct
- Check bucket permissions

### Files Not Persisting
- Verify `USE_S3=true` in Streamlit Cloud secrets
- Check app logs for S3 errors
- Verify bucket name and credentials

## Migration

Your existing local data won't automatically migrate to S3. Options:

1. **Fresh start**: Just deploy and start fresh on Streamlit Cloud
2. **Manual migration**: Use AWS CLI to upload existing files:
   ```bash
   aws s3 sync profile_analyses/ s3://your-bucket/midjourney-profiles/profile_analyses/
   aws s3 sync profile_results/ s3://your-bucket/midjourney-profiles/profile_results/
   aws s3 cp test_prompts.json s3://your-bucket/midjourney-profiles/
   ```

## Next Steps

1. Create S3 bucket
2. Create IAM user and save credentials
3. Add secrets to Streamlit Cloud
4. Deploy and test!

Your files will now persist across all Streamlit Cloud restarts! 🎉
