
import os

LICENSE_HEADER = """/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
"""

FILES_TO_UPDATE = [
    "ArrayReverser.java",
    "ArrayManipulator.java",
    "PrimitiveArrayConverter.java",
    "ArraySearchAndRemoval.java",
    "ArrayLengthUtils.java",
    "ArraySubarrayExtractor.java"
]

BASE_DIR = "/Users/uditanshutomar/commons-lang/src/main/java/org/apache/commons/lang3"

def main():
    print(f"Scanning {BASE_DIR}...")
    count = 0
    for root, dirs, files in os.walk(BASE_DIR):
        for filename in files:
            if not filename.endswith(".java"):
                continue
                
            file_path = os.path.join(root, filename)
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            if "Licensed to the Apache Software Foundation" in content:
                continue
                
            print(f"Adding license to {filename}...")
            new_content = LICENSE_HEADER + content
            
            with open(file_path, 'w') as f:
                f.write(new_content)
            count += 1
            
    print(f"Updated {count} files.")

if __name__ == "__main__":
    main()
