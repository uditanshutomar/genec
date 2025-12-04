# Stage 6 Verification Tools - Installation & Setup Guide

## Overview

Stage 6 implements **7-layer verification** with external tool integration. For production use, you should install the actual tools, not rely on fallbacks.

---

## ⚠️ Current Status

| Tool | Status | Impact |
|------|--------|--------|
| **Maven** | ✅ Installed | Equivalence checking **WORKS** |
| **PMD** | ❌ Not installed | Static analysis **DISABLED** (fallback) |
| **SpotBugs** | ❌ Not installed | Bug detection **DISABLED** (fallback) |
| **SonarQube** | ❌ Not installed | Code quality **DISABLED** (fallback) |
| **Java 8/11/17/21** | ❌ Not installed | Multi-version **DISABLED** (fallback) |

**Current behavior**: Tests pass because of graceful degradation, BUT main verification logic isn't running.

---

## 🎯 Recommended Setup (Production-Ready)

### 1. PMD Installation

```bash
# macOS (Homebrew)
brew install pmd

# Verify
pmd --version
```

**Alternative (Manual)**:
```bash
wget https://github.com/pmd/pmd/releases/download/pmd_releases%2F7.0.0/pmd-dist-7.0.0-bin.zip
unzip pmd-dist-7.0.0-bin.zip
export PATH=$PATH:$PWD/pmd-bin-7.0.0/bin
```

### 2. SpotBugs Installation

```bash
# macOS (Homebrew)
brew install spotbugs

# Verify
spotbugs -version
```

**Alternative (Manual)**:
```bash
wget https://repo.maven.apache.org/maven2/com/github/spotbugs/spotbugs/4.8.3/spotbugs-4.8.3.zip
unzip spotbugs-4.8.3.zip
export PATH=$PATH:$PWD/spotbugs-4.8.3/bin
```

### 3. SonarQube Installation

**Option A: Docker (Recommended)**
```bash
docker run -d --name sonarqube -p 9000:9000 sonarqube:latest

# SonarQube Scanner
brew install sonar-scanner

# Verify
sonar-scanner --version
```

**Option B: Manual**
```bash
wget https://binaries.sonarsource.com/Distribution/sonarqube/sonarqube-10.3.zip
unzip sonarqube-10.3.zip
./sonarqube-10.3/bin/macosx-universal-64/sonar.sh start
```

### 4. Multi-Version Java

```bash
# Install SDKMAN (Java version manager)
curl -s "https://get.sdkman.io" | bash
source "$HOME/.sdkman/bin/sdkman-init.sh"

# Install multiple Java versions
sdk install java 8.0.392-tem
sdk install java 11.0.21-tem
sdk install java 17.0.9-tem
sdk install java 21.0.1-tem

# Verify
sdk list java
```

---

## 🧪 Verification Commands

### Test PMD
```bash
cd /path/to/java/project
pmd check -d src/main/java -R category/java/bestpractices.xml -f json
```

### Test SpotBugs
```bash
cd /path/to/java/project
mvn compile  # Compile first
spotbugs -textui target/classes
```

### Test SonarQube
```bash
cd /path/to/java/project
sonar-scanner \
  -Dsonar.projectKey=test-project \
  -Dsonar.sources=src/main/java \
  -Dsonar.host.url=http://localhost:9000 \
  -Dsonar.login=admin \
  -Dsonar.password=admin
```

### Test Multi-Version Java
```bash
# Compile with Java 8
sdk use java 8.0.392-tem
javac -version  # Should show 1.8

# Compile with Java 11
sdk use java 11.0.21-tem
javac -version  # Should show 11

# Compile with Java 17
sdk use java 17.0.9-tem
javac -version  # Should show 17

# Compile with Java 21
sdk use java 21.0.1-tem
javac -version  # Should show 21
```

---

## 📊 Expected Results (After Installation)

```
================================================================================
STAGE 6 VERIFICATION TOOLS - STATUS CHECK
================================================================================

✅ Maven: Available (v3.9.x)
✅ PMD: Available (v7.0.x)
✅ SpotBugs: Available (v4.8.x)
✅ SonarQube: Available (Server running on :9000)
✅ Java 8: Available
✅ Java 11: Available
✅ Java 17: Available
✅ Java 21: Available

🎉 ALL TOOLS INSTALLED - MAIN LOGIC ACTIVE
```

---

## ⚙️ Configuration

Update `genec/config/config.yaml`:

```yaml
verification:
  # Layer 0: Equivalence
  enable_equivalence: true
  
  # Layer 1: Syntactic
  enable_syntactic: true
  
  # Layer 1.5: Static Analysis (NOW ENABLED)
  enable_static_analysis: true
  sonarqube_url: "http://localhost:9000"
  sonarqube_token: "your-token-here"
  
  # Layer 1.7: Multi-Version (NOW ENABLED)
  enable_multiversion: true
  java_versions:
    - "8"
    - "11"
    - "17"
    - "21"
  
  # Layer 2: Semantic
  enable_semantic: true
  
  # Layer 3: Behavioral
  enable_behavioral: true
  
  # Layer 4: Performance (NOW ENABLED)
  enable_performance: true
  max_regression_percent: 5.0
```

---

## 🚨 Minimal vs Production Setup

### Minimal (Development/Testing)
```yaml
# Uses fallbacks - tests will pass but tools won't run
verification:
  enable_equivalence: true   # ✅ Works with Maven
  enable_syntactic: true     # ✅ Works with javac
  enable_static_analysis: false  # ❌ Disabled
  enable_multiversion: false     # ❌ Disabled
  enable_semantic: true     # ✅ Works natively
  enable_behavioral: true   # ✅ Works with Maven
  enable_performance: false # ❌ Disabled
```

### Production (Full Verification)
```yaml
# All tools installed - full verification
verification:
  enable_equivalence: true   # ✅ Maven
  enable_syntactic: true     # ✅ javac
  enable_static_analysis: true   # ✅ PMD + SpotBugs + SonarQube
  enable_multiversion: true      # ✅ Java 8/11/17/21
  enable_semantic: true     # ✅ Native
  enable_behavioral: true   # ✅ Maven
  enable_performance: true  # ✅ Maven benchmarks
```

---

## 🎯 Priority Installation Order

1. **Maven** (Required for equivalence) - ✅ Already installed
2. **PMD** (Static analysis) - Install next
3. **SpotBugs** (Bug detection) - Install next
4. **SonarQube** (Code quality) - Optional but recommended
5. **Multi-Java** (Compatibility) - Optional but recommended

---

## 📝 Quick Start (macOS)

```bash
# Install all tools (5 minutes)
brew install pmd spotbugs sonar-scanner

# Start SonarQube
docker run -d --name sonarqube -p 9000:9000 sonarqube:latest

# Install Java versions (10 minutes)
curl -s "https://get.sdkman.io" | bash
source "$HOME/.sdkman/bin/sdkman-init.sh"
sdk install java 8.0.392-tem
sdk install java 11.0.21-tem
sdk install java 17.0.9-tem
sdk install java 21.0.1-tem

# Verify all tools
pmd --version
spotbugs -version
sonar-scanner --version
sdk list java

# Run full verification test
python3 examples/test_stage6_verification.py
```

Expected output:
```
✅ PMD: Available
✅ SpotBugs: Available
✅ SonarQube: Available
✅ Java versions: 8, 11, 17, 21
```

---

## 🔍 Debugging

If tools still show as unavailable:

```bash
# Check PATH
echo $PATH

# Check installations
which pmd
which spotbugs
which sonar-scanner
which javac

# Check permissions
ls -la $(which pmd)
```

---

## 💡 Alternative: CI/CD Integration

In CI/CD, use Docker images with all tools pre-installed:

```dockerfile
FROM maven:3.9-eclipse-temurin-21

# Install PMD
RUN wget https://github.com/pmd/pmd/releases/download/pmd_releases%2F7.0.0/pmd-dist-7.0.0-bin.zip && \
    unzip pmd-dist-7.0.0-bin.zip && \
    mv pmd-bin-7.0.0 /opt/pmd && \
    ln -s /opt/pmd/bin/pmd /usr/local/bin/pmd

# Install SpotBugs
RUN wget https://repo.maven.apache.org/maven2/com/github/spotbugs/spotbugs/4.8.3/spotbugs-4.8.3.zip && \
    unzip spotbugs-4.8.3.zip && \
    mv spotbugs-4.8.3 /opt/spotbugs && \
    ln -s /opt/spotbugs/bin/spotbugs /usr/local/bin/spotbugs

# Install SonarQube Scanner
RUN wget https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip && \
    unzip sonar-scanner-cli-5.0.1.3006-linux.zip && \
    mv sonar-scanner-5.0.1.3006-linux /opt/sonar-scanner && \
    ln -s /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner

# Install multiple Java versions (using adoptium-temurin)
# Java 8, 11, 17 already in base image

# Install GenEC
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
```

---

## ✅ Success Criteria

After setup, running GenEC should show:

```
Stage 6 Verification Results:
  Layer 0 (Equivalence): ✅ 42 tests passed
  Layer 1 (Syntactic): ✅ Compiled successfully
  Layer 1.5 (Static Analysis):
    - PMD: ✅ 0 violations
    - SpotBugs: ✅ 0 bugs
    - SonarQube: ✅ Quality gate passed
  Layer 1.7 (Multi-Version):
    - Java 8: ✅ Compiled
    - Java 11: ✅ Compiled
    - Java 17: ✅ Compiled
    - Java 21: ✅ Compiled
  Layer 2 (Semantic): ✅ Passed
  Layer 3 (Behavioral): ✅ All tests green
  Layer 4 (Performance): ✅ No regression (-2.3%)
```

**This is the production-ready setup!**
