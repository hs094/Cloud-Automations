#!/usr/bin/env python3
"""
Script to push all variables from .env file to AWS SSM Parameter Store or Secrets Manager.
Usage: python push.py --profile <profile_name> --tag <tag> [--env-file <path>] [--target <target>]

COST INFORMATION:
- SSM Parameter Store:
  * Standard parameters: $0.05 per 10,000 parameters (free tier includes 10,000)
  * Advanced parameters: $0.06 per 10,000 parameters + $0.05 per GB/month
  * SecureString parameters: Additional $0.05 per 10,000 API calls
- Secrets Manager:
  * $0.40 per secret per month
  * $0.05 per 10,000 API calls
  * Free tier includes 1 secret and 100,000 API calls per month

RECOMMENDATION:
- Use SSM Parameter Store for configuration variables, API keys, tokens
- Use Secrets Manager for highly sensitive data like database passwords, certificates
"""

import sys
import logging
from pathlib import Path
import argparse

try:
    import boto3
except ImportError:
    print("Error: boto3 is required. Install it with: pip install boto3")
    sys.exit(1)


def parse_env_file(env_path):
    """Parse .env file and return dictionary of variables."""
    env_vars = {}
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)

    with open(env_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse key=value pairs
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                env_vars[key] = value
            else:
                print(f"Warning: Invalid line {line_num}: {line}")

    return env_vars


def push_to_ssm(env_vars, profile_name, tag):
    """Push environment variables to AWS SSM Parameter Store."""
    try:
        # Create boto3 session with specified profile
        logging.info(f"Creating boto3 session with profile: {profile_name}")
        session = boto3.Session(profile_name=profile_name)

        # Get session details
        credentials = session.get_credentials()
        region = session.region_name
        logging.info(f"Session created successfully")
        logging.info(f"Region: {region}")
        logging.info(f"Credentials type: {type(credentials).__name__}")

        if credentials:
            logging.info(
                f"Access key: {credentials.access_key[:8]}...{credentials.access_key[-4:]}"
            )
            logging.info(
                f"Secret key: {credentials.secret_key[:8]}...{credentials.secret_key[-4:]}"
            )
            if credentials.token:
                logging.info(f"Session token: {credentials.token[:20]}...")
        else:
            logging.warning("No credentials found in session")

        ssm = session.client("ssm")
        logging.info(f"SSM client created for region: {ssm.meta.region_name}")

        print(f"Using AWS profile: {profile_name}")
        print(f"Tag: {tag}")
        print(f"Found {len(env_vars)} environment variables to push")
        print(f"AWS Region: {region}")
        print(f"SSM Endpoint: {ssm.meta.endpoint_url}")

        # Push each variable to SSM
        logging.info(f"Starting to push {len(env_vars)} parameters to SSM")
        for key, value in env_vars.items():
            parameter_name = f"/{tag}/{key}"
            logging.info(f"Processing parameter: {parameter_name}")

            try:
                # Check if parameter already exists
                try:
                    logging.debug(f"Checking if parameter exists: {parameter_name}")
                    ssm.get_parameter(Name=parameter_name)
                    parameter_exists = True
                    logging.info(f"Parameter already exists: {parameter_name}")
                except ssm.exceptions.ParameterNotFound:
                    parameter_exists = False
                    logging.info(
                        f"Parameter does not exist, will create: {parameter_name}"
                    )

                param_type = (
                    "SecureString"
                    if any(
                        secret in key.lower()
                        for secret in ["password", "secret", "key", "token"]
                    )
                    else "String"
                )
                logging.info(f"Parameter type for {parameter_name}: {param_type}")

                tags = [
                    {"Key": "Source", "Value": ".env"},
                    {"Key": "Profile", "Value": profile_name},
                    {"Key": "Tag", "Value": tag},
                ]

                if parameter_exists:
                    # Update existing parameter (no tags allowed)
                    logging.info(f"Updating existing parameter: {parameter_name}")
                    response = ssm.put_parameter(
                        Name=parameter_name,
                        Value=value,
                        Type=param_type,
                        Overwrite=True,
                    )
                else:
                    # Create new parameter with tags
                    logging.info(f"Creating new parameter with tags: {parameter_name}")
                    response = ssm.put_parameter(
                        Name=parameter_name,
                        Value=value,
                        Type=param_type,
                        Tags=tags,
                    )
                logging.info(f"Successfully pushed parameter: {parameter_name}")
                logging.debug(f"Response: {response}")
                print(f"✓ Pushed: {parameter_name}")
            except Exception as e:
                logging.error(f"Failed to push {parameter_name}: {str(e)}")
                print(f"✗ Failed to push {parameter_name}: {str(e)}")

        print(f"\nCompleted pushing {len(env_vars)} parameters to SSM")
        logging.info(
            f"Successfully completed pushing {len(env_vars)} parameters to SSM"
        )

        # Log region information for console visibility
        print(f"\n=== AWS Region Information ===")
        print(f"Parameters were stored in region: {region}")
        print(f"To view these parameters in AWS Console:")
        print(f"1. Go to AWS Systems Manager -> Parameter Store")
        print(f"2. Make sure you're in the correct region: {region}")
        print(f"3. Look for parameters with prefix: /{tag}/")
        print(f"===============================")

    except Exception as e:
        logging.error(f"Failed to connect to AWS SSM: {str(e)}")
        print(f"Error: Failed to connect to AWS SSM: {str(e)}")
        sys.exit(1)


def push_to_secrets_manager(env_vars, profile_name, tag):
    """Push environment variables to AWS Secrets Manager."""
    try:
        # Create boto3 session with specified profile
        logging.info(f"Creating boto3 session with profile: {profile_name}")
        session = boto3.Session(profile_name=profile_name)

        # Get session details
        credentials = session.get_credentials()
        region = session.region_name
        logging.info(f"Session created successfully")
        logging.info(f"Region: {region}")
        logging.info(f"Credentials type: {type(credentials).__name__}")

        if credentials:
            logging.info(
                f"Access key: {credentials.access_key[:8]}...{credentials.access_key[-4:]}"
            )
            logging.info(
                f"Secret key: {credentials.secret_key[:8]}...{credentials.secret_key[-4:]}"
            )
            if credentials.token:
                logging.info(f"Session token: {credentials.token[:20]}...")
        else:
            logging.warning("No credentials found in session")

        secretsmanager = session.client("secretsmanager")
        logging.info(
            f"Secrets Manager client created for region: {secretsmanager.meta.region_name}"
        )

        print(f"Using AWS profile: {profile_name}")
        print(f"Tag: {tag}")
        print(f"Found {len(env_vars)} environment variables to push")
        print(f"AWS Region: {region}")
        print(f"Secrets Manager Endpoint: {secretsmanager.meta.endpoint_url}")

        # Push each variable to Secrets Manager
        logging.info(f"Starting to push {len(env_vars)} secrets to Secrets Manager")
        for key, value in env_vars.items():
            secret_name = f"{tag}/{key}"
            logging.info(f"Processing secret: {secret_name}")

            try:
                # Check if secret already exists
                try:
                    logging.debug(f"Checking if secret exists: {secret_name}")
                    secretsmanager.describe_secret(SecretId=secret_name)
                    secret_exists = True
                    logging.info(f"Secret already exists: {secret_name}")
                except secretsmanager.exceptions.ResourceNotFoundException:
                    secret_exists = False
                    logging.info(f"Secret does not exist, will create: {secret_name}")

                # Create secret string as JSON
                secret_string = f'{{"{key}": "{value}"}}'

                tags = [
                    {"Key": "Source", "Value": ".env"},
                    {"Key": "Profile", "Value": profile_name},
                    {"Key": "Tag", "Value": tag},
                ]

                if secret_exists:
                    # Update existing secret
                    logging.info(f"Updating existing secret: {secret_name}")
                    response = secretsmanager.update_secret(
                        SecretId=secret_name,
                        SecretString=secret_string,
                    )
                else:
                    # Create new secret with tags
                    logging.info(f"Creating new secret with tags: {secret_name}")
                    response = secretsmanager.create_secret(
                        Name=secret_name,
                        SecretString=secret_string,
                        Tags=tags,
                    )
                logging.info(f"Successfully pushed secret: {secret_name}")
                logging.debug(f"Response: {response}")
                print(f"✓ Pushed: {secret_name}")
            except Exception as e:
                logging.error(f"Failed to push {secret_name}: {str(e)}")
                print(f"✗ Failed to push {secret_name}: {str(e)}")

        print(f"\nCompleted pushing {len(env_vars)} secrets to Secrets Manager")
        logging.info(
            f"Successfully completed pushing {len(env_vars)} secrets to Secrets Manager"
        )

        # Log region information for console visibility
        print(f"\n=== AWS Region Information ===")
        print(f"Secrets were stored in region: {region}")
        print(f"To view these secrets in AWS Console:")
        print(f"1. Go to AWS Secrets Manager")
        print(f"2. Make sure you're in the correct region: {region}")
        print(f"3. Look for secrets with prefix: {tag}/")
        print(f"===============================")

    except Exception as e:
        logging.error(f"Failed to connect to AWS Secrets Manager: {str(e)}")
        print(f"Error: Failed to connect to AWS Secrets Manager: {str(e)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Push .env variables to AWS SSM Parameter Store or Secrets Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python push.py --profile my-profile --tag myapp --target ssm
  python push.py --profile my-profile --tag myapp --target secretsmanager --env-file ./config/.env
  python push.py --profile my-profile --tag myapp --target ssm --env-file ./prod.env
        """,
    )

    parser.add_argument("--profile", required=True, help="AWS profile name to use")
    parser.add_argument(
        "--tag", required=True, help="Tag to use for parameter/secret hierarchy"
    )
    parser.add_argument(
        "--target",
        choices=["ssm", "secretsmanager"],
        default="ssm",
        help="Target service: ssm (Parameter Store) or secretsmanager (Secrets Manager) (default: ssm)",
    )
    parser.add_argument(
        "--env-file", default=".env", help="Path to .env file (default: .env)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("push_ssm.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logging.info(
        f"Starting push script with profile: {args.profile}, tag: {args.tag}, target: {args.target}"
    )

    # Parse .env file
    env_path = Path(args.env_file)
    env_vars = parse_env_file(env_path)

    if not env_vars:
        print("No environment variables found in .env file")
        sys.exit(1)

    # Push to selected target
    if args.target == "ssm":
        push_to_ssm(env_vars, args.profile, args.tag)
    elif args.target == "secretsmanager":
        push_to_secrets_manager(env_vars, args.profile, args.tag)


if __name__ == "__main__":
    main()
