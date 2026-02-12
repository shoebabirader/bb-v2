"""Deploy trading bot to EC2 instance"""
import subprocess
import sys

# EC2 connection details
EC2_HOST = "3.80.58.47"
EC2_USER = "ubuntu"
PEM_KEY = "BB.pem"
REPO_URL = "https://github.com/shoebabirader/bb-v2.git"

def run_ssh_command(command, description):
    """Run a command on EC2 via SSH"""
    print(f"\n{'='*80}")
    print(f"STEP: {description}")
    print(f"{'='*80}")
    
    ssh_cmd = f'ssh -i {PEM_KEY} {EC2_USER}@{EC2_HOST} "{command}"'
    print(f"Running: {command}\n")
    
    result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"[WARNING] Command exited with code {result.returncode}")
    else:
        print("[OK] Command completed successfully")
    
    return result.returncode == 0

def main():
    print("="*80)
    print("DEPLOYING TRADING BOT TO EC2")
    print("="*80)
    
    # Step 1: Clone repository
    run_ssh_command(
        "cd ~ && rm -rf bb-v2 && git clone https://github.com/shoebabirader/bb-v2.git",
        "Clone repository from GitHub"
    )
    
    # Step 2: Create virtual environment
    run_ssh_command(
        "cd ~/bb-v2 && python3 -m venv venv",
        "Create Python virtual environment"
    )
    
    # Step 3: Install Python dependencies
    run_ssh_command(
        "cd ~/bb-v2 && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt",
        "Install Python dependencies"
    )
    
    # Step 4: Create config directory
    run_ssh_command(
        "cd ~/bb-v2 && mkdir -p config logs",
        "Create config and logs directories"
    )
    
    print("\n" + "="*80)
    print("DEPLOYMENT COMPLETE!")
    print("="*80)
    print("\nNEXT STEPS:")
    print("1. Upload your config.json file to EC2:")
    print(f"   scp -i {PEM_KEY} config/config.json {EC2_USER}@{EC2_HOST}:~/bb-v2/config/")
    print("\n2. SSH into EC2 and test the bot:")
    print(f"   ssh -i {PEM_KEY} {EC2_USER}@{EC2_HOST}")
    print("   cd bb-v2")
    print("   source venv/bin/activate")
    print("   python main.py")
    print("\n3. Run bot in background with screen:")
    print("   screen -S trading-bot")
    print("   source venv/bin/activate")
    print("   python main.py")
    print("   # Press Ctrl+A then D to detach")
    print("   # Use 'screen -r trading-bot' to reattach")
    print("="*80)

if __name__ == "__main__":
    main()
