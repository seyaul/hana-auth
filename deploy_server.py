#!/usr/bin/env python3
"""
Server Release Script - Run this in your server directory
Usage: python deploy_server.py 1.0.1 "Fixed menu hover issues"
"""

import sys
import subprocess
import os
import re
from datetime import datetime

def run_command(cmd, check=True):
    """Run a command and print output"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result

def update_server_version(version, changelog):
    """Update version info in app.py"""
    
    if not os.path.exists("app.py"):
        print("❌ Error: app.py not found in current directory")
        return False
    
    # Read with explicit UTF-8 encoding
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Update CURRENT_VERSION
    content = re.sub(
        r'CURRENT_VERSION = "[^"]*"',
        f'CURRENT_VERSION = "{version}"',
        content
    )
    
    # Update download URL to point to zip file
    content = re.sub(
        r'download/v[^/]*/HanaTool[^"]*\.exe',
        f'download/v{version}/HanaTool-{version}.zip',
        content
    )
    
    # Update release date
    today = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(
        r'"release_date": "[^"]*"',
        f'"release_date": "{today}"',
        content
    )
    
    # Update changelog
    safe_changelog = changelog.replace('"', '\\"')
    content = re.sub(
        r'"changelog": "[^"]*"',
        f'"changelog": "{safe_changelog}"',
        content
    )
    
    # Write back to file
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Updated app.py with version {version}")
    return True

def deploy_server(version, changelog):
    """Deploy server with updated version info"""
    
    print(f"🚁 Deploying HanaTool Server v{version}")
    print(f"📝 Changelog: {changelog}")
    print("-" * 50)
    
    # Step 1: Update version in app.py
    print("📝 Step 1: Updating version in app.py...")
    if not update_server_version(version, changelog):
        return False
    
    # Step 2: Commit changes
    print("📝 Step 2: Committing server updates...")
    run_command("git add app.py", check=False)
    run_command(f'git commit -m "Update server to support v{version}"', check=False)
    run_command("git push", check=False)
    
    # Step 3: Deploy to Fly.io
    print("🚁 Step 3: Deploying to Fly.io...")
    result = run_command("fly deploy")
    
    if result.returncode != 0:
        print("❌ Failed to deploy to Fly.io")
        return False
    
    # Step 4: Verify deployment
    print("✅ Step 4: Verifying deployment...")
    print("Waiting 10 seconds for deployment to complete...")
    import time
    time.sleep(10)
    
    # Try to verify with requests, but don't fail if not available
    try:
        import requests
        response = requests.get("https://hana-auth.fly.dev/version", timeout=15)
        if response.status_code == 200:
            data = response.json()
            deployed_version = data.get("version")
            if deployed_version == version:
                print(f"✅ Server deployed successfully!")
                print(f"🌐 Version endpoint: https://hana-auth.fly.dev/version")
                print(f"📱 Deployed version: {deployed_version}")
                print(f"📦 Download URL: {data.get('download_url')}")
            else:
                print(f"⚠️  Warning: Server shows version {deployed_version}, expected {version}")
                print("This might be a caching issue. Try again in a few minutes.")
        else:
            print(f"⚠️  Warning: Server returned status {response.status_code}")
    except ImportError:
        print("⚠️  Requests library not available - skipping automatic verification")
        print("✅ Deployment completed, but verification skipped")
        print("📝 Manually verify with: curl https://hana-auth.fly.dev/version")
        print("    or visit: https://hana-auth.fly.dev/version in your browser")
    except Exception as e:
        print(f"⚠️  Warning: Could not verify server deployment: {e}")
        print("Server might still be starting up. Check manually:")
        print("curl https://hana-auth.fly.dev/version")
    
    print("-" * 50)
    print(f"🎉 Server deployment complete!")
    print()
    print("📱 Your users will now see the update notification when they open the app!")
    
    return True

def main():
    if len(sys.argv) != 3:
        print("Usage: python deploy_server.py <version> <changelog>")
        print("Example: python deploy_server.py 1.0.1 'Fixed menu hover issues'")
        print()
        print("Note: Make sure you've already deployed the GUI with this version!")
        return
    
    version = sys.argv[1]
    changelog = sys.argv[2]
    
    # Validate version format
    if not all(part.isdigit() for part in version.split('.')):
        print("❌ Error: Version should be in format X.Y.Z (e.g., 1.0.1)")
        return
    
    # Check if we're in the right directory
    if not os.path.exists("fly.toml"):
        print("❌ Error: fly.toml not found. Are you in the server directory?")
        return
    
    # Confirm deployment
    print(f"About to deploy server for version {version}")
    print(f"Changelog: {changelog}")
    print()
    print("⚠️  Make sure you've already:")
    print("   1. Built and released the GUI v{version}")
    print("   2. Created the GitHub release")
    print()
    confirm = input("Continue with server deployment? (y/N): ")
    
    if confirm.lower() != 'y':
        print("Deployment cancelled.")
        return
    
    # Run deployment
    deploy_server(version, changelog)

if __name__ == "__main__":
    main()