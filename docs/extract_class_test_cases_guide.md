# Extract Class Test Cases: Implementation Guide

**Purpose:** Practical guide for creating and evaluating Extract Class refactoring test cases
**Target Audience:** Tool developers, researchers, QA engineers
**Date:** 2025-12-05

---

## Table of Contents

1. [Test Case Design Principles](#1-test-case-design-principles)
2. [Sample Test Cases by Difficulty](#2-sample-test-cases-by-difficulty)
3. [Ground Truth Definition](#3-ground-truth-definition)
4. [Evaluation Automation](#4-evaluation-automation)
5. [Common Test Patterns](#5-common-test-patterns)

---

## 1. Test Case Design Principles

### 1.1 Realism Requirements

A realistic God Class test case must:

1. **Represent Real Code Smells**
   - Authentic mixing of responsibilities
   - Realistic method and field naming
   - Actual business logic patterns
   - NOT artificially constructed examples

2. **Have Clear but Non-Trivial Extractions**
   - Not immediately obvious (requires analysis)
   - Multiple valid solutions may exist
   - Some ambiguous cases
   - Reasonable disagreement possible

3. **Include Edge Cases**
   - Shared field dependencies
   - Method call chains across groups
   - Utility methods (unclear placement)
   - Polymorphic behavior

4. **Be Testable**
   - Compilable code
   - Runnable test suite
   - Measurable metrics
   - Verifiable correctness

### 1.2 Size Guidelines

| Difficulty | LOC | Methods | Fields | Cohesive Groups | Notes |
|------------|-----|---------|--------|-----------------|-------|
| Easy | 150-250 | 10-15 | 6-10 | 2-3 | Clear data clumps, obvious separation |
| Medium | 250-450 | 15-25 | 10-15 | 3-4 | Some interdependencies, mixed concerns |
| Hard | 450-700 | 25-40 | 15-25 | 4-6 | Complex dependencies, subtle semantics |
| Very Hard | 700+ | 40+ | 25+ | 5+ | Real-world complexity, multiple challenges |

### 1.3 Metric Targets for Test God Classes

To qualify as a good test case God Class:

```
LOC > 200
WMC > 30
LCOM5 > 0.6
TCC < 0.4
Number of cohesive groups >= 3
```

---

## 2. Sample Test Cases by Difficulty

### 2.1 Easy: Library Book Manager

**Characteristics:**
- Clear data clumps (Book, Member, Loan)
- Minimal interdependencies
- Obvious extraction points

```java
/**
 * EASY TEST CASE: LibraryBookManager
 * Expected extractions: Book, Member, Loan
 * LOC: ~200
 * Difficulty: 1/5
 */
public class LibraryBookManager {
    // Book data - EXTRACT to Book class
    private String isbn;
    private String title;
    private String author;
    private int publicationYear;
    private boolean isAvailable;

    // Member data - EXTRACT to Member class
    private String memberId;
    private String memberName;
    private String memberEmail;
    private Date membershipExpiry;

    // Loan data - EXTRACT to Loan class
    private Date loanDate;
    private Date dueDate;
    private boolean isReturned;

    // Book methods - COHESIVE GROUP 1
    public void setBookInfo(String isbn, String title, String author, int year) {
        this.isbn = isbn;
        this.title = title;
        this.author = author;
        this.publicationYear = year;
    }

    public String getBookDetails() {
        return String.format("%s by %s (%d)", title, author, publicationYear);
    }

    public boolean isBookAvailable() {
        return isAvailable;
    }

    public void markAsAvailable() {
        this.isAvailable = true;
    }

    public void markAsUnavailable() {
        this.isAvailable = false;
    }

    // Member methods - COHESIVE GROUP 2
    public void registerMember(String id, String name, String email) {
        this.memberId = id;
        this.memberName = name;
        this.memberEmail = email;
        this.membershipExpiry = calculateExpiryDate();
    }

    public boolean isMembershipValid() {
        return membershipExpiry != null && membershipExpiry.after(new Date());
    }

    public String getMemberInfo() {
        return String.format("%s (%s)", memberName, memberId);
    }

    private Date calculateExpiryDate() {
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.YEAR, 1);
        return cal.getTime();
    }

    // Loan methods - COHESIVE GROUP 3
    public void issueLoan() {
        this.loanDate = new Date();
        this.dueDate = calculateDueDate();
        this.isReturned = false;
        markAsUnavailable();
    }

    public void returnBook() {
        this.isReturned = true;
        markAsAvailable();
    }

    public boolean isOverdue() {
        return !isReturned && new Date().after(dueDate);
    }

    private Date calculateDueDate() {
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.DAY_OF_MONTH, 14);
        return cal.getTime();
    }

    public int getDaysOverdue() {
        if (!isOverdue()) return 0;
        long diff = new Date().getTime() - dueDate.getTime();
        return (int) (diff / (1000 * 60 * 60 * 24));
    }
}
```

**Expected Refactored Structure:**

```java
public class Book {
    private String isbn;
    private String title;
    private String author;
    private int publicationYear;
    private boolean isAvailable;

    // Book methods...
}

public class Member {
    private String memberId;
    private String memberName;
    private String memberEmail;
    private Date membershipExpiry;

    // Member methods...
}

public class Loan {
    private Book book;
    private Member member;
    private Date loanDate;
    private Date dueDate;
    private boolean isReturned;

    // Loan methods...
}

public class LibraryService {
    // Orchestration methods using Book, Member, Loan
}
```

**Evaluation Criteria:**
- ✅ Should extract all 3 classes
- ✅ Each class should have LCOM5 < 0.3
- ✅ Coupling between extracted classes should be minimal
- ✅ Names should match domain concepts

### 2.2 Medium: E-Commerce Shopping Cart

**Characteristics:**
- Multiple responsibilities (cart, pricing, payment, shipping)
- Some shared dependencies
- Mix of data and service extractions

```java
/**
 * MEDIUM TEST CASE: ShoppingCartManager
 * Expected extractions: CartItems, PriceCalculator, PaymentProcessor, ShippingCalculator
 * LOC: ~350
 * Difficulty: 3/5
 */
public class ShoppingCartManager {
    // Cart data - EXTRACT to CartItems
    private List<CartItem> items = new ArrayList<>();
    private String cartId;

    // Customer data - SHARED DEPENDENCY (challenge!)
    private String customerId;
    private String customerEmail;

    // Pricing data - EXTRACT to PriceCalculator
    private double taxRate = 0.08;
    private String discountCode;
    private double discountAmount;

    // Payment data - EXTRACT to PaymentProcessor
    private String paymentMethod;
    private String cardLastFour;
    private boolean paymentProcessed;

    // Shipping data - EXTRACT to ShippingCalculator
    private String shippingAddress;
    private String shippingMethod;
    private double shippingCost;

    // Cart item management - COHESIVE GROUP 1
    public void addItem(String productId, String name, double price, int quantity) {
        CartItem item = new CartItem(productId, name, price, quantity);
        items.add(item);
    }

    public void removeItem(String productId) {
        items.removeIf(item -> item.getProductId().equals(productId));
    }

    public void updateQuantity(String productId, int newQuantity) {
        for (CartItem item : items) {
            if (item.getProductId().equals(productId)) {
                item.setQuantity(newQuantity);
            }
        }
    }

    public int getTotalItems() {
        return items.stream().mapToInt(CartItem::getQuantity).sum();
    }

    public List<CartItem> getItems() {
        return new ArrayList<>(items);
    }

    // Pricing calculations - COHESIVE GROUP 2
    public double calculateSubtotal() {
        return items.stream()
            .mapToDouble(item -> item.getPrice() * item.getQuantity())
            .sum();
    }

    public double calculateTax() {
        return calculateSubtotal() * taxRate;
    }

    public void applyDiscountCode(String code) {
        this.discountCode = code;
        this.discountAmount = calculateDiscount(code);
    }

    private double calculateDiscount(String code) {
        double subtotal = calculateSubtotal();
        // Simplified discount logic
        if ("SAVE10".equals(code)) return subtotal * 0.1;
        if ("SAVE20".equals(code)) return subtotal * 0.2;
        return 0.0;
    }

    public double calculateTotal() {
        double subtotal = calculateSubtotal();
        double tax = calculateTax();
        return subtotal + tax - discountAmount + shippingCost;
    }

    // Payment processing - COHESIVE GROUP 3
    public boolean processPayment(String method, String cardNumber) {
        this.paymentMethod = method;
        this.cardLastFour = cardNumber.substring(cardNumber.length() - 4);

        // Simulate payment processing
        boolean success = validatePaymentMethod(method) && chargeCard(cardNumber, calculateTotal());

        if (success) {
            this.paymentProcessed = true;
        }
        return success;
    }

    private boolean validatePaymentMethod(String method) {
        return "CREDIT_CARD".equals(method) || "DEBIT_CARD".equals(method);
    }

    private boolean chargeCard(String cardNumber, double amount) {
        // Simulate successful charge
        return cardNumber != null && amount > 0;
    }

    public boolean isPaymentCompleted() {
        return paymentProcessed;
    }

    // Shipping calculation - COHESIVE GROUP 4
    public void setShippingMethod(String method) {
        this.shippingMethod = method;
        this.shippingCost = calculateShippingCost(method);
    }

    private double calculateShippingCost(String method) {
        double weight = getTotalWeight();
        if ("EXPRESS".equals(method)) return 15.0 + (weight * 2.0);
        if ("STANDARD".equals(method)) return 5.0 + (weight * 0.5);
        return 0.0; // Free shipping
    }

    private double getTotalWeight() {
        // Simplified: assume each item weighs 1 unit
        return getTotalItems() * 1.0;
    }

    public String getEstimatedDelivery() {
        if ("EXPRESS".equals(shippingMethod)) return "2-3 business days";
        if ("STANDARD".equals(shippingMethod)) return "5-7 business days";
        return "7-10 business days";
    }

    // Customer methods - AMBIGUOUS (could extract or stay)
    public void setCustomerInfo(String customerId, String email) {
        this.customerId = customerId;
        this.customerEmail = email;
    }

    public String getCustomerId() {
        return customerId;
    }

    // Utility method - AMBIGUOUS
    public String generateOrderSummary() {
        return String.format("Order for %s: %d items, Total: $%.2f",
            customerId, getTotalItems(), calculateTotal());
    }

    // Inner class for cart items
    private static class CartItem {
        private String productId;
        private String name;
        private double price;
        private int quantity;

        public CartItem(String productId, String name, double price, int quantity) {
            this.productId = productId;
            this.name = name;
            this.price = price;
            this.quantity = quantity;
        }

        // Getters and setters...
        public String getProductId() { return productId; }
        public double getPrice() { return price; }
        public int getQuantity() { return quantity; }
        public void setQuantity(int quantity) { this.quantity = quantity; }
    }
}
```

**Expected Extractions (Multiple Valid Solutions):**

**Solution 1: Aggressive Extraction**
```java
- CartItemCollection (5 methods, high cohesion)
- PriceCalculator (5 methods, stateless service)
- PaymentProcessor (4 methods, payment logic)
- ShippingCalculator (3 methods, shipping logic)
- ShoppingCart (orchestration + customer info)
```

**Solution 2: Conservative Extraction**
```java
- CartItemCollection (cart management)
- PricingService (pricing + discounts + tax)
- PaymentService (payment + shipping combined)
- ShoppingCart (orchestration)
```

**Challenges in This Test:**
1. **Shared dependency**: `customerId` used by multiple groups
2. **Method interdependency**: `calculateTotal()` calls multiple groups
3. **Ambiguous placement**: `generateOrderSummary()` could go anywhere
4. **Service vs. Data**: Some extractions are data (CartItems), others services

### 2.3 Hard: User Account Manager

**Characteristics:**
- Complex interdependencies
- Temporal coupling (registration flow)
- Polymorphic behavior (different account types)
- Security concerns (password, permissions)

```java
/**
 * HARD TEST CASE: UserAccountManager
 * Expected extractions: 4-6 classes depending on approach
 * LOC: ~500
 * Difficulty: 4/5
 * Challenges: Temporal coupling, polymorphism, security
 */
public class UserAccountManager {
    // User profile data
    private String userId;
    private String username;
    private String email;
    private String firstName;
    private String lastName;
    private Date dateOfBirth;
    private String phoneNumber;

    // Authentication data
    private String passwordHash;
    private String passwordSalt;
    private Date lastPasswordChange;
    private int failedLoginAttempts;
    private boolean accountLocked;
    private Date lockoutExpiry;

    // Account type & permissions
    private AccountType accountType; // BASIC, PREMIUM, ADMIN
    private Set<Permission> permissions;
    private Date subscriptionExpiry;
    private String subscriptionTier;

    // Profile settings
    private String profilePictureUrl;
    private String bio;
    private boolean emailNotifications;
    private boolean smsNotifications;
    private String preferredLanguage;
    private String timezone;

    // Activity tracking
    private Date lastLoginDate;
    private String lastLoginIp;
    private int loginCount;
    private List<String> loginHistory;

    // Billing information
    private String billingAddress;
    private String paymentMethodId;
    private Date nextBillingDate;
    private double accountBalance;

    // === COHESIVE GROUP 1: Profile Management ===
    public void updateProfile(String firstName, String lastName, String phone) {
        this.firstName = firstName;
        this.lastName = lastName;
        this.phoneNumber = phone;
    }

    public String getFullName() {
        return firstName + " " + lastName;
    }

    public void updateProfilePicture(String url) {
        this.profilePictureUrl = url;
    }

    public void updateBio(String bio) {
        this.bio = bio;
    }

    public boolean isProfileComplete() {
        return firstName != null && lastName != null && email != null && phoneNumber != null;
    }

    public int getAge() {
        if (dateOfBirth == null) return 0;
        Calendar birth = Calendar.getInstance();
        birth.setTime(dateOfBirth);
        Calendar now = Calendar.getInstance();
        int age = now.get(Calendar.YEAR) - birth.get(Calendar.YEAR);
        if (now.get(Calendar.DAY_OF_YEAR) < birth.get(Calendar.DAY_OF_YEAR)) {
            age--;
        }
        return age;
    }

    // === COHESIVE GROUP 2: Authentication ===
    public boolean authenticate(String password) {
        if (accountLocked && lockoutExpiry.after(new Date())) {
            return false;
        }

        String hashedPassword = hashPassword(password, passwordSalt);
        if (hashedPassword.equals(passwordHash)) {
            failedLoginAttempts = 0;
            recordSuccessfulLogin();
            return true;
        } else {
            recordFailedLogin();
            return false;
        }
    }

    private void recordSuccessfulLogin() {
        this.lastLoginDate = new Date();
        this.loginCount++;
        if (loginHistory == null) loginHistory = new ArrayList<>();
        loginHistory.add("Success: " + new Date());
    }

    private void recordFailedLogin() {
        this.failedLoginAttempts++;
        if (failedLoginAttempts >= 5) {
            lockAccount();
        }
        if (loginHistory == null) loginHistory = new ArrayList<>();
        loginHistory.add("Failed: " + new Date());
    }

    private void lockAccount() {
        this.accountLocked = true;
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.HOUR, 24);
        this.lockoutExpiry = cal.getTime();
    }

    public void resetPassword(String newPassword) {
        this.passwordSalt = generateSalt();
        this.passwordHash = hashPassword(newPassword, passwordSalt);
        this.lastPasswordChange = new Date();
        this.failedLoginAttempts = 0;
    }

    private String hashPassword(String password, String salt) {
        // Simplified hashing
        return (password + salt).hashCode() + "";
    }

    private String generateSalt() {
        return UUID.randomUUID().toString();
    }

    public boolean isPasswordExpired() {
        if (lastPasswordChange == null) return true;
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.DAY_OF_MONTH, -90); // 90 days
        return lastPasswordChange.before(cal.getTime());
    }

    // === COHESIVE GROUP 3: Authorization / Permissions ===
    public boolean hasPermission(Permission permission) {
        if (permissions == null) return false;
        return permissions.contains(permission);
    }

    public void grantPermission(Permission permission) {
        if (permissions == null) permissions = new HashSet<>();
        permissions.add(permission);
    }

    public void revokePermission(Permission permission) {
        if (permissions != null) {
            permissions.remove(permission);
        }
    }

    public boolean canAccessAdminPanel() {
        return accountType == AccountType.ADMIN;
    }

    public boolean canEditContent() {
        return hasPermission(Permission.EDIT) || accountType == AccountType.ADMIN;
    }

    // === COHESIVE GROUP 4: Subscription Management ===
    public void upgradeToPremium() {
        this.accountType = AccountType.PREMIUM;
        this.subscriptionTier = "Premium";
        this.subscriptionExpiry = calculateSubscriptionExpiry();
        grantPremiumPermissions();
    }

    public void downgradeToBasic() {
        this.accountType = AccountType.BASIC;
        this.subscriptionTier = "Basic";
        this.subscriptionExpiry = null;
        revokePremiumPermissions();
    }

    private Date calculateSubscriptionExpiry() {
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.MONTH, 1);
        return cal.getTime();
    }

    public boolean isSubscriptionActive() {
        return subscriptionExpiry != null && subscriptionExpiry.after(new Date());
    }

    private void grantPremiumPermissions() {
        grantPermission(Permission.PREMIUM_FEATURE);
        grantPermission(Permission.ADVANCED_ANALYTICS);
    }

    private void revokePremiumPermissions() {
        revokePermission(Permission.PREMIUM_FEATURE);
        revokePermission(Permission.ADVANCED_ANALYTICS);
    }

    // === COHESIVE GROUP 5: Preferences ===
    public void updateNotificationSettings(boolean email, boolean sms) {
        this.emailNotifications = email;
        this.smsNotifications = sms;
    }

    public void updateLocaleSettings(String language, String timezone) {
        this.preferredLanguage = language;
        this.timezone = timezone;
    }

    public boolean shouldSendEmailNotification() {
        return emailNotifications && email != null;
    }

    // === COHESIVE GROUP 6: Billing ===
    public void updateBillingAddress(String address) {
        this.billingAddress = address;
    }

    public void addPaymentMethod(String methodId) {
        this.paymentMethodId = methodId;
    }

    public void chargeAccount(double amount) {
        this.accountBalance -= amount;
        updateNextBillingDate();
    }

    private void updateNextBillingDate() {
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.MONTH, 1);
        this.nextBillingDate = cal.getTime();
    }

    public double getAccountBalance() {
        return accountBalance;
    }

    // === TEMPORAL COUPLING CHALLENGE ===
    // This method orchestrates multiple groups - should NOT be extracted
    public boolean completeRegistration(String password, AccountType type) {
        // Validation (profile)
        if (!isProfileComplete()) return false;

        // Set authentication (auth)
        resetPassword(password);

        // Set account type (subscription)
        this.accountType = type;
        if (type == AccountType.PREMIUM) {
            upgradeToPremium();
        }

        // Initialize settings (preferences)
        updateNotificationSettings(true, false);
        updateLocaleSettings("en", "UTC");

        return true;
    }

    // Enums
    enum AccountType { BASIC, PREMIUM, ADMIN }
    enum Permission { READ, WRITE, EDIT, DELETE, PREMIUM_FEATURE, ADVANCED_ANALYTICS }
}
```

**Expected Extractions (Expert Solution):**

```java
// 1. User Profile
class UserProfile {
    private String userId;
    private String firstName, lastName;
    private String email, phoneNumber;
    private Date dateOfBirth;
    private String profilePictureUrl, bio;
    // Profile methods...
}

// 2. Authentication Manager
class AuthenticationManager {
    private String passwordHash, passwordSalt;
    private Date lastPasswordChange;
    private int failedLoginAttempts;
    private boolean accountLocked;
    private Date lockoutExpiry;
    // Auth methods...
}

// 3. Authorization Manager
class AuthorizationManager {
    private AccountType accountType;
    private Set<Permission> permissions;
    // Permission methods...
}

// 4. Subscription Service
class SubscriptionService {
    private String subscriptionTier;
    private Date subscriptionExpiry;
    // Subscription methods...
}

// 5. User Preferences
class UserPreferences {
    private boolean emailNotifications, smsNotifications;
    private String preferredLanguage, timezone;
    // Preference methods...
}

// 6. Billing Information
class BillingInfo {
    private String billingAddress;
    private String paymentMethodId;
    private Date nextBillingDate;
    private double accountBalance;
    // Billing methods...
}

// 7. Account orchestrator
class UserAccount {
    private UserProfile profile;
    private AuthenticationManager auth;
    private AuthorizationManager authz;
    private SubscriptionService subscription;
    private UserPreferences preferences;
    private BillingInfo billing;

    // Orchestration methods like completeRegistration()
}
```

**Challenges:**
1. **Temporal coupling**: `completeRegistration()` uses multiple groups sequentially
2. **Polymorphism**: Different account types have different behaviors
3. **Security**: Password/auth data should be isolated
4. **Interdependencies**: Subscription affects permissions, auth affects login tracking

---

## 3. Ground Truth Definition

### 3.1 Expert Annotation Format

```json
{
  "test_case": "ShoppingCartManager",
  "difficulty": "medium",
  "god_class_metrics": {
    "loc": 350,
    "methods": 22,
    "fields": 13,
    "wmc": 45,
    "lcom5": 0.72,
    "tcc": 0.28
  },
  "expected_extractions": [
    {
      "class_name": "CartItemCollection",
      "priority": "high",
      "methods": ["addItem", "removeItem", "updateQuantity", "getTotalItems", "getItems"],
      "fields": ["items", "cartId"],
      "rationale": "Cohesive cart item management responsibility",
      "cohesion_score": 0.95
    },
    {
      "class_name": "PriceCalculator",
      "priority": "high",
      "methods": ["calculateSubtotal", "calculateTax", "applyDiscountCode", "calculateDiscount", "calculateTotal"],
      "fields": ["taxRate", "discountCode", "discountAmount"],
      "rationale": "Pricing logic is distinct business concern",
      "cohesion_score": 0.88
    },
    {
      "class_name": "PaymentProcessor",
      "priority": "medium",
      "methods": ["processPayment", "validatePaymentMethod", "chargeCard", "isPaymentCompleted"],
      "fields": ["paymentMethod", "cardLastFour", "paymentProcessed"],
      "rationale": "Payment processing should be isolated for security and testing",
      "cohesion_score": 0.90
    },
    {
      "class_name": "ShippingCalculator",
      "priority": "medium",
      "methods": ["setShippingMethod", "calculateShippingCost", "getTotalWeight", "getEstimatedDelivery"],
      "fields": ["shippingAddress", "shippingMethod", "shippingCost"],
      "rationale": "Shipping logic is separate business concern",
      "cohesion_score": 0.85
    }
  ],
  "ambiguous_elements": [
    {
      "element": "setCustomerInfo",
      "type": "method",
      "options": ["Extract to Customer class", "Keep in orchestrator"],
      "notes": "Could go either way depending on whether Customer is a separate entity"
    },
    {
      "element": "generateOrderSummary",
      "type": "method",
      "options": ["Keep in orchestrator", "Extract to OrderSummary class"],
      "notes": "Utility method that uses multiple concerns - likely stays"
    }
  ],
  "evaluation_weights": {
    "precision": 0.4,
    "recall": 0.3,
    "cohesion_improvement": 0.15,
    "coupling_minimization": 0.15
  }
}
```

### 3.2 Multiple Expert Agreement

Best practice: Have 3-5 experts independently annotate, then:

1. **Calculate agreement rate**:
   ```
   Agreement = (Extractions agreed by all experts) / (Total unique extractions suggested)
   ```

2. **Use consensus extractions**:
   - High confidence: 100% agreement (all experts)
   - Medium confidence: 60-80% agreement (most experts)
   - Low confidence: <60% agreement (ambiguous cases)

3. **Document disagreements**:
   - Record rationale for different opinions
   - Use as discussion points for evaluation
   - May indicate legitimate alternative solutions

---

## 4. Evaluation Automation

### 4.1 Complete Evaluation Script

```python
#!/usr/bin/env python3
"""
Extract Class Refactoring Evaluator
Compares tool output against ground truth
"""

import json
from typing import Dict, List, Set
from dataclasses import dataclass

@dataclass
class ExtractionProposal:
    """Represents a proposed extraction"""
    class_name: str
    methods: Set[str]
    fields: Set[str]
    confidence: float = 1.0

@dataclass
class GroundTruthExtraction:
    """Ground truth extraction from expert"""
    class_name: str
    methods: Set[str]
    fields: Set[str]
    priority: str  # high, medium, low
    rationale: str

class ExtractionEvaluator:
    """Evaluates Extract Class proposals against ground truth"""

    def __init__(self, ground_truth_file: str):
        with open(ground_truth_file) as f:
            self.ground_truth = json.load(f)

    def evaluate(self, proposals: List[ExtractionProposal]) -> Dict:
        """
        Evaluate proposals against ground truth

        Returns:
            Dict with precision, recall, f1, and detailed analysis
        """
        gt_extractions = self._load_ground_truth_extractions()
        results = {
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
            'true_positives': [],
            'false_positives': [],
            'false_negatives': [],
            'partial_matches': [],
            'metrics': {}
        }

        # Match proposals to ground truth
        matched_gt = set()
        for proposal in proposals:
            best_match, match_score = self._find_best_match(proposal, gt_extractions)

            if match_score >= 0.7:  # High match threshold
                results['true_positives'].append({
                    'proposed': proposal.class_name,
                    'ground_truth': best_match.class_name if best_match else None,
                    'match_score': match_score
                })
                if best_match:
                    matched_gt.add(best_match.class_name)
            elif match_score >= 0.3:  # Partial match
                results['partial_matches'].append({
                    'proposed': proposal.class_name,
                    'ground_truth': best_match.class_name if best_match else None,
                    'match_score': match_score,
                    'issues': self._identify_issues(proposal, best_match)
                })
            else:
                results['false_positives'].append({
                    'proposed': proposal.class_name,
                    'reason': 'No corresponding ground truth extraction'
                })

        # Find missed extractions
        for gt in gt_extractions:
            if gt.class_name not in matched_gt:
                results['false_negatives'].append({
                    'expected': gt.class_name,
                    'priority': gt.priority,
                    'methods': list(gt.methods),
                    'rationale': gt.rationale
                })

        # Calculate metrics
        tp = len(results['true_positives'])
        fp = len(results['false_positives'])
        fn = len(results['false_negatives'])

        results['precision'] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        results['recall'] = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        results['f1_score'] = (2 * results['precision'] * results['recall'] /
                               (results['precision'] + results['recall'])
                               if (results['precision'] + results['recall']) > 0 else 0.0)

        return results

    def _load_ground_truth_extractions(self) -> List[GroundTruthExtraction]:
        """Load ground truth extractions from JSON"""
        extractions = []
        for ext in self.ground_truth['expected_extractions']:
            extractions.append(GroundTruthExtraction(
                class_name=ext['class_name'],
                methods=set(ext['methods']),
                fields=set(ext['fields']),
                priority=ext['priority'],
                rationale=ext['rationale']
            ))
        return extractions

    def _find_best_match(self, proposal: ExtractionProposal,
                        gt_extractions: List[GroundTruthExtraction]) -> tuple:
        """Find best matching ground truth extraction"""
        best_match = None
        best_score = 0.0

        for gt in gt_extractions:
            score = self._calculate_match_score(proposal, gt)
            if score > best_score:
                best_score = score
                best_match = gt

        return best_match, best_score

    def _calculate_match_score(self, proposal: ExtractionProposal,
                               gt: GroundTruthExtraction) -> float:
        """
        Calculate similarity score between proposal and ground truth

        Uses Jaccard similarity on methods + fields
        """
        # Method overlap
        proposed_methods = proposal.methods
        gt_methods = gt.methods
        method_jaccard = (len(proposed_methods & gt_methods) /
                         len(proposed_methods | gt_methods)
                         if len(proposed_methods | gt_methods) > 0 else 0.0)

        # Field overlap
        proposed_fields = proposal.fields
        gt_fields = gt.fields
        field_jaccard = (len(proposed_fields & gt_fields) /
                        len(proposed_fields | gt_fields)
                        if len(proposed_fields | gt_fields) > 0 else 0.0)

        # Combined score (weight methods more heavily)
        score = 0.7 * method_jaccard + 0.3 * field_jaccard

        # Bonus for exact class name match
        if self._normalize_name(proposal.class_name) == self._normalize_name(gt.class_name):
            score += 0.1

        return min(1.0, score)

    def _normalize_name(self, name: str) -> str:
        """Normalize class name for comparison"""
        return name.lower().replace('_', '').replace('-', '')

    def _identify_issues(self, proposal: ExtractionProposal,
                        gt: GroundTruthExtraction) -> List[str]:
        """Identify specific issues with partial match"""
        issues = []

        missing_methods = gt.methods - proposal.methods
        if missing_methods:
            issues.append(f"Missing methods: {missing_methods}")

        extra_methods = proposal.methods - gt.methods
        if extra_methods:
            issues.append(f"Extra methods: {extra_methods}")

        missing_fields = gt.fields - proposal.fields
        if missing_fields:
            issues.append(f"Missing fields: {missing_fields}")

        extra_fields = proposal.fields - gt.fields
        if extra_fields:
            issues.append(f"Extra fields: {extra_fields}")

        return issues

    def generate_report(self, results: Dict) -> str:
        """Generate human-readable evaluation report"""
        report = []
        report.append("=" * 60)
        report.append("EXTRACT CLASS REFACTORING EVALUATION REPORT")
        report.append("=" * 60)
        report.append("")

        # Summary metrics
        report.append("SUMMARY METRICS:")
        report.append(f"  Precision: {results['precision']:.2%}")
        report.append(f"  Recall:    {results['recall']:.2%}")
        report.append(f"  F1-Score:  {results['f1_score']:.2%}")
        report.append("")

        # True positives
        if results['true_positives']:
            report.append(f"TRUE POSITIVES ({len(results['true_positives'])}):")
            for tp in results['true_positives']:
                report.append(f"  ✓ {tp['proposed']} (match: {tp['match_score']:.2%})")
            report.append("")

        # False positives
        if results['false_positives']:
            report.append(f"FALSE POSITIVES ({len(results['false_positives'])}):")
            for fp in results['false_positives']:
                report.append(f"  ✗ {fp['proposed']}: {fp['reason']}")
            report.append("")

        # False negatives
        if results['false_negatives']:
            report.append(f"FALSE NEGATIVES ({len(results['false_negatives'])}):")
            for fn in results['false_negatives']:
                report.append(f"  ⚠ {fn['expected']} (priority: {fn['priority']})")
                report.append(f"    Rationale: {fn['rationale']}")
            report.append("")

        # Partial matches
        if results['partial_matches']:
            report.append(f"PARTIAL MATCHES ({len(results['partial_matches'])}):")
            for pm in results['partial_matches']:
                report.append(f"  ~ {pm['proposed']} → {pm['ground_truth']} (score: {pm['match_score']:.2%})")
                for issue in pm['issues']:
                    report.append(f"      - {issue}")
            report.append("")

        report.append("=" * 60)
        return "\n".join(report)


# Example usage
if __name__ == "__main__":
    # Example proposals from a tool
    proposals = [
        ExtractionProposal(
            class_name="CartItems",
            methods={"addItem", "removeItem", "updateQuantity", "getTotalItems"},
            fields={"items", "cartId"},
            confidence=0.95
        ),
        ExtractionProposal(
            class_name="PriceCalculator",
            methods={"calculateSubtotal", "calculateTax", "calculateTotal"},
            fields={"taxRate"},
            confidence=0.88
        ),
        # Missing applyDiscountCode - will be partial match
    ]

    evaluator = ExtractionEvaluator("ground_truth.json")
    results = evaluator.evaluate(proposals)
    print(evaluator.generate_report(results))
```

### 4.2 Metric Calculation Functions

```python
def calculate_lcom5(class_data: Dict) -> float:
    """
    Calculate LCOM5 metric
    """
    methods = class_data['methods']
    fields = class_data['fields']
    field_accesses = class_data['field_accesses']  # Dict[method_name, Set[field_name]]

    m = len(methods)
    a = len(fields)

    if m <= 1 or a == 0:
        return 0.0

    # Count methods accessing each field
    sum_mA = sum(
        len([method for method in methods if field in field_accesses.get(method, set())])
        for field in fields
    )

    lcom5 = (m - sum_mA / a) / (m - 1)
    return max(0.0, min(1.0, lcom5))


def calculate_tcc(class_data: Dict) -> float:
    """
    Calculate TCC (Tight Class Cohesion)
    """
    methods = class_data['methods']
    field_accesses = class_data['field_accesses']
    method_calls = class_data['method_calls']  # Dict[method_name, Set[called_method_name]]

    m = len(methods)
    if m <= 1:
        return 0.0

    # Count directly connected pairs
    ndc = 0
    for i in range(m):
        for j in range(i + 1, m):
            method1 = methods[i]
            method2 = methods[j]

            # Check field sharing
            fields1 = field_accesses.get(method1, set())
            fields2 = field_accesses.get(method2, set())
            if fields1 & fields2:
                ndc += 1
                continue

            # Check method calls
            calls1 = method_calls.get(method1, set())
            calls2 = method_calls.get(method2, set())
            if method2 in calls1 or method1 in calls2:
                ndc += 1

    np = m * (m - 1) // 2
    return ndc / np if np > 0 else 0.0


def calculate_cbo(class_data: Dict, all_class_names: Set[str]) -> int:
    """
    Calculate CBO (Coupling Between Objects)
    """
    coupled_classes = set()

    # From field types
    for field_type in class_data.get('field_types', []):
        if field_type in all_class_names:
            coupled_classes.add(field_type)

    # From method return types
    for return_type in class_data.get('return_types', []):
        if return_type in all_class_names:
            coupled_classes.add(return_type)

    # From parameter types
    for param_type in class_data.get('parameter_types', []):
        if param_type in all_class_names:
            coupled_classes.add(param_type)

    # Remove self-reference
    coupled_classes.discard(class_data['class_name'])

    return len(coupled_classes)
```

---

## 5. Common Test Patterns

### 5.1 Pattern: Data Clump Detection

**Test Input:**
```java
class Order {
    private String customerName;
    private String customerEmail;
    private String customerPhone;
    // ... more customer fields used together
}
```

**Expected Detection:**
- Tool should identify these 3+ fields as a data clump
- Propose `Customer` class extraction
- Include all methods that primarily use these fields

**Evaluation:**
- ✅ Correctly identifies all clump members
- ✅ Proposes meaningful class name
- ✅ Includes appropriate methods
- ❌ Misses some clump members
- ❌ Includes unrelated fields

### 5.2 Pattern: Feature Envy

**Test Input:**
```java
class Report {
    private Customer customer;

    public String generateCustomerSection() {
        return customer.getName() + "\n" +
               customer.getEmail() + "\n" +
               customer.getAddress() + "\n" +
               customer.getPhone();
    }
}
```

**Expected Detection:**
- Method accesses Customer more than Report data
- Propose moving method to Customer class
- Alternative: Extract to CustomerFormatter

**Evaluation:**
- ✅ Detects feature envy
- ✅ Proposes appropriate move
- ❌ Doesn't detect (false negative)
- ❌ Proposes extraction when move is better

### 5.3 Pattern: Service Extraction

**Test Input:**
```java
class ShoppingCart {
    public double calculateSubtotal() { ... }
    public double calculateTax() { ... }
    public double calculateShipping() { ... }
    public double calculateTotal() { ... }
}
```

**Expected Detection:**
- Identify calculation methods as cohesive unit
- Propose service class (stateless or minimal state)
- Name should reflect purpose (e.g., PriceCalculator)

**Evaluation:**
- ✅ Groups all calculation methods
- ✅ Proposes service-style class
- ✅ Good naming (Calculator, Service, Processor)
- ❌ Mixes calculations with other responsibilities
- ❌ Poor naming (Utils, Helper)

### 5.4 Pattern: Strategy Extraction

**Test Input:**
```java
class PaymentProcessor {
    public boolean processPayment(String type, double amount) {
        if ("CREDIT_CARD".equals(type)) {
            // Credit card logic
        } else if ("PAYPAL".equals(type)) {
            // PayPal logic
        } else if ("CRYPTO".equals(type)) {
            // Crypto logic
        }
    }
}
```

**Expected Detection (Advanced):**
- Identify polymorphic behavior
- Propose Strategy pattern
- Extract CreditCardPayment, PayPalPayment, CryptoPayment

**Evaluation:**
- ✅ Recognizes strategy pattern opportunity
- ✅ Creates interface/abstract class
- ✅ Separate implementation classes
- ⚠️ Simple extraction (acceptable but not optimal)
- ❌ Doesn't recognize pattern

---

## Summary Checklist

### Creating a Test Case

- [ ] LOC between 200-700
- [ ] WMC > 30
- [ ] LCOM5 > 0.6
- [ ] At least 3 cohesive groups
- [ ] Mix of easy and challenging extractions
- [ ] Includes at least one edge case
- [ ] Compilable and testable
- [ ] Realistic naming and logic

### Defining Ground Truth

- [ ] Expert annotations completed
- [ ] Expected extractions documented with rationale
- [ ] Ambiguous cases noted
- [ ] Priority levels assigned
- [ ] Multiple experts (3-5) if possible
- [ ] Agreement rate calculated

### Evaluation Setup

- [ ] Metrics calculation implemented
- [ ] Precision/recall formulas correct
- [ ] Ground truth comparison logic
- [ ] Partial match handling
- [ ] Report generation
- [ ] Test suite automated

### Running Evaluation

- [ ] Tool output parsed correctly
- [ ] Metrics calculated for original class
- [ ] Metrics calculated for extracted classes
- [ ] Comparison against ground truth
- [ ] Report generated
- [ ] Results reviewed by experts

---

**End of Guide**
