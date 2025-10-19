# GenEC Example

This document demonstrates a complete example of using GenEC to refactor a "god class".

## Example God Class

Consider this Java class that violates the Single Responsibility Principle:

```java
package com.example.ecommerce;

public class Customer {
    // Personal information
    private String firstName;
    private String lastName;
    private String email;
    private String phoneNumber;

    // Address information
    private String street;
    private String city;
    private String state;
    private String zipCode;

    // Account information
    private String accountId;
    private double accountBalance;
    private String creditCardNumber;

    // Order history
    private List<Order> orderHistory;
    private double totalSpent;

    public Customer(String firstName, String lastName, String email) {
        this.firstName = firstName;
        this.lastName = lastName;
        this.email = email;
        this.orderHistory = new ArrayList<>();
        this.totalSpent = 0.0;
    }

    // Personal info methods
    public String getFullName() {
        return firstName + " " + lastName;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPhoneNumber() {
        return phoneNumber;
    }

    public void setPhoneNumber(String phoneNumber) {
        this.phoneNumber = phoneNumber;
    }

    // Address methods
    public String getFullAddress() {
        return street + ", " + city + ", " + state + " " + zipCode;
    }

    public void updateAddress(String street, String city, String state, String zipCode) {
        this.street = street;
        this.city = city;
        this.state = state;
        this.zipCode = zipCode;
    }

    // Account methods
    public void deposit(double amount) {
        accountBalance += amount;
    }

    public boolean withdraw(double amount) {
        if (accountBalance >= amount) {
            accountBalance -= amount;
            return true;
        }
        return false;
    }

    public double getAccountBalance() {
        return accountBalance;
    }

    // Order methods
    public void addOrder(Order order) {
        orderHistory.add(order);
        totalSpent += order.getTotal();
    }

    public List<Order> getOrderHistory() {
        return new ArrayList<>(orderHistory);
    }

    public double getTotalSpent() {
        return totalSpent;
    }
}
```

## Running GenEC

### Step 1: Prepare the Environment

```bash
# Set API key
export ANTHROPIC_API_KEY='your-api-key-here'

# Initialize Git repository (if not already)
cd /path/to/project
git init
git add .
git commit -m "Initial commit"
```

### Step 2: Run GenEC Pipeline

```python
from genec.core.pipeline import GenECPipeline

# Initialize
pipeline = GenECPipeline('config/config.yaml')

# Run on Customer class
result = pipeline.run_full_pipeline(
    class_file='src/main/java/com/example/ecommerce/Customer.java',
    repo_path='/path/to/project',
    max_suggestions=3
)

# View results
print(f"Generated {len(result.verified_suggestions)} verified suggestions")
```

### Step 3: Review Suggestions

GenEC might identify these cohesive clusters:

**Cluster 1: Address Information**
- Fields: `street`, `city`, `state`, `zipCode`
- Methods: `getFullAddress()`, `updateAddress()`

**Cluster 2: Account Information**
- Fields: `accountId`, `accountBalance`, `creditCardNumber`
- Methods: `deposit()`, `withdraw()`, `getAccountBalance()`

**Cluster 3: Order Management**
- Fields: `orderHistory`, `totalSpent`
- Methods: `addOrder()`, `getOrderHistory()`, `getTotalSpent()`

## Expected Output

### Suggestion 1: Extract Address Class

**Rationale:**
"The address-related fields and methods form a cohesive unit responsible for managing customer location information. Extracting this into a separate Address class follows the Single Responsibility Principle and improves separation of concerns, making the code more maintainable and reusable."

**New Class: CustomerAddress.java**

```java
package com.example.ecommerce;

public class CustomerAddress {
    private String street;
    private String city;
    private String state;
    private String zipCode;

    public CustomerAddress() {
    }

    public CustomerAddress(String street, String city, String state, String zipCode) {
        this.street = street;
        this.city = city;
        this.state = state;
        this.zipCode = zipCode;
    }

    public String getFullAddress() {
        return street + ", " + city + ", " + state + " " + zipCode;
    }

    public void updateAddress(String street, String city, String state, String zipCode) {
        this.street = street;
        this.city = city;
        this.state = state;
        this.zipCode = zipCode;
    }

    // Getters and setters
    public String getStreet() { return street; }
    public void setStreet(String street) { this.street = street; }

    public String getCity() { return city; }
    public void setCity(String city) { this.city = city; }

    public String getState() { return state; }
    public void setState(String state) { this.state = state; }

    public String getZipCode() { return zipCode; }
    public void setZipCode(String zipCode) { this.zipCode = zipCode; }
}
```

**Modified Original: Customer.java**

```java
package com.example.ecommerce;

public class Customer {
    // Personal information
    private String firstName;
    private String lastName;
    private String email;
    private String phoneNumber;

    // Address (delegated to CustomerAddress)
    private CustomerAddress address;

    // Account information
    private String accountId;
    private double accountBalance;
    private String creditCardNumber;

    // Order history
    private List<Order> orderHistory;
    private double totalSpent;

    public Customer(String firstName, String lastName, String email) {
        this.firstName = firstName;
        this.lastName = lastName;
        this.email = email;
        this.address = new CustomerAddress();
        this.orderHistory = new ArrayList<>();
        this.totalSpent = 0.0;
    }

    // Delegate address methods
    public String getFullAddress() {
        return address.getFullAddress();
    }

    public void updateAddress(String street, String city, String state, String zipCode) {
        address.updateAddress(street, city, state, zipCode);
    }

    // ... rest of the methods ...
}
```

## Verification Results

Each suggestion goes through three verification layers:

###  Layer 1: Syntactic Verification
- Both classes compile successfully
- No syntax errors

###  Layer 2: Semantic Verification
- All extracted members exist in original class
- Extracted members correctly moved to new class
- Proper delegation maintained in original class

###  Layer 3: Behavioral Verification
- All existing tests pass
- No behavioral changes detected

## Quality Metrics Comparison

**Before Refactoring:**
- LCOM5: 0.72 (high lack of cohesion)
- CBO: 3
- Methods: 14
- Fields: 11

**After Refactoring (Customer + CustomerAddress):**
- Customer LCOM5: 0.45 (improved cohesion)
- CustomerAddress LCOM5: 0.12 (highly cohesive)
- Average CBO: 2.5 (reduced coupling)

## Benefits

1. **Improved Cohesion**: Each class has a single, well-defined responsibility
2. **Better Reusability**: Address class can be reused in other contexts
3. **Easier Testing**: Address logic can be tested independently
4. **Enhanced Maintainability**: Changes to address handling are localized
5. **Reduced Complexity**: Each class is simpler and easier to understand

## Running from Command Line

```bash
python scripts/run_pipeline.py \
  --class-file src/main/java/com/example/ecommerce/Customer.java \
  --repo-path /path/to/project \
  --max-suggestions 3 \
  --output-dir refactorings/customer

# View results
ls refactorings/customer/
# CustomerAddress.java
# Customer_modified_1.java
# genec.log
```

## Next Steps

1. Review the generated code
2. Apply the refactoring to your codebase
3. Run your test suite
4. Update any dependent code
5. Commit the refactored code
