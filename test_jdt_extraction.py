#!/usr/bin/env python3
"""
Test script to verify JDT method extraction - captures stderr.
"""
import json
import subprocess
import os

# Path to JDT wrapper JAR
jdt_jar = "/Users/uditanshutomar/genec/genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"

# Simple test spec
spec = {
    'projectPath': '/Users/uditanshutomar/commons-lang-fresh',
    'classFile': '/Users/uditanshutomar/commons-lang-fresh/src/main/java/org/apache/commons/lang3/EnumUtils.java',
    'newClassName': 'TestExtractedClass',
    'methods': [
        'isEnum(Class)',
        'stream(Class)'
    ],
    'fields': []
}

spec_json = json.dumps(spec)
cmd = ['java', '-jar', jdt_jar, '--spec', spec_json]

print("Running JDT refactoring test...")
print(f"Methods to extract: {spec['methods']}")
print()

result = subprocess.run(cmd, capture_output=True, text=True)

print("=" * 80)
print("STDERR OUTPUT:")
print("=" * 80)
print(result.stderr)
print()

if result.returncode == 0:
    response = json.loads(result.stdout)
    if response.get('success'):
        print("✓ Refactoring successful!")
        print()
        print("=" * 80)
        print("NEW CLASS CODE:")
        print("=" * 80)
        print(response['newClassCode'])
    else:
        print(f"✗ Refactoring failed: {response.get('message')}")
else:
    print(f"✗ JDT process failed with exit code {result.returncode}")
    print(f"stdout: {result.stdout}")
