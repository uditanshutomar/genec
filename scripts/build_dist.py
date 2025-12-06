import subprocess
import sys
import shutil
from pathlib import Path
import os

def build_dist():
    """Build the standalone GenEC executable."""
    root_dir = Path(__file__).parent.parent
    dist_dir = root_dir / "dist"
    
    print(f"Building GenEC from {root_dir}")
    
    # Clean dist
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    # Check for JDT JAR
    jar_path = root_dir / "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"
    if not jar_path.exists():
        print("Warning: JDT JAR not found. Please run 'mvn clean package' in genec-jdt-wrapper first.")
        # We continue, but the binary won't have the JAR bundled unless it's built
    
    cmd = [
        "pyinstaller",
        "--name=genec",
        "--onefile",
        "--clean",
        # Add config directory
        "--add-data=genec/config:genec/config",
        # Add JDT JAR if it exists
        f"--add-data={jar_path}:genec-jdt-wrapper/target" if jar_path.exists() else None,
        "genec/cli.py"
    ]
    
    # Filter out None
    cmd = [c for c in cmd if c is not None]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=root_dir, check=True)
    
    print(f"Build complete. Executable is at {dist_dir / 'genec'}")

if __name__ == "__main__":
    build_dist()
