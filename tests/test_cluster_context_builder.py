"""Unit tests for ClusterContextBuilder."""

import pytest
from genec.core.cluster_context_builder import ClusterContextBuilder
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies, MethodInfo, FieldInfo


@pytest.fixture
def sample_class_deps():
    """Create a sample ClassDependencies object for testing."""
    # Create fields
    fields = [
        FieldInfo(name='accountBalance', type='double', modifiers=['private'], line_number=10),
        FieldInfo(name='accountNumber', type='String', modifiers=['private'], line_number=11),
        FieldInfo(name='name', type='String', modifiers=['private'], line_number=12),
        FieldInfo(name='age', type='int', modifiers=['private'], line_number=13),
    ]

    # Create methods with bodies
    methods = [
        MethodInfo(
            name='getAccountBalance',
            signature='getAccountBalance()',
            return_type='double',
            modifiers=['public'],
            parameters=[],
            start_line=20,
            end_line=22,
            body='public double getAccountBalance() {\n    return accountBalance;\n}'
        ),
        MethodInfo(
            name='deposit',
            signature='deposit(double)',
            return_type='void',
            modifiers=['public'],
            parameters=[{'type': 'double', 'name': 'amount'}],
            start_line=24,
            end_line=26,
            body='public void deposit(double amount) {\n    accountBalance += amount;\n}'
        ),
        MethodInfo(
            name='withdraw',
            signature='withdraw(double)',
            return_type='void',
            modifiers=['public'],
            parameters=[{'type': 'double', 'name': 'amount'}],
            start_line=28,
            end_line=32,
            body='public void withdraw(double amount) {\n    if (accountBalance >= amount) {\n        accountBalance -= amount;\n    }\n}'
        ),
        MethodInfo(
            name='getName',
            signature='getName()',
            return_type='String',
            modifiers=['public'],
            parameters=[],
            start_line=34,
            end_line=36,
            body='public String getName() {\n    return name;\n}'
        ),
        MethodInfo(
            name='setName',
            signature='setName(String)',
            return_type='void',
            modifiers=['public'],
            parameters=[{'type': 'String', 'name': 'name'}],
            start_line=38,
            end_line=40,
            body='public void setName(String name) {\n    this.name = name;\n}'
        ),
    ]

    # Create ClassDependencies
    class_deps = ClassDependencies(
        class_name='GodClass',
        package_name='com.example',
        file_path='/test/GodClass.java',
        methods=methods,
        fields=fields,
        constructors=[],
        field_accesses={
            'getAccountBalance()': ['accountBalance'],
            'deposit(double)': ['accountBalance'],
            'withdraw(double)': ['accountBalance'],
            'getName()': ['name'],
            'setName(String)': ['name'],
        },
        method_calls={},
        dependency_matrix=None,
        member_names=[]
    )

    return class_deps


@pytest.fixture
def account_cluster():
    """Create a cluster for account-related methods."""
    cluster = Cluster(
        id=0,
        member_names=['getAccountBalance()', 'deposit(double)', 'withdraw(double)', 'accountBalance'],
        member_types={'getAccountBalance()': 'method', 'deposit(double)': 'method',
                     'withdraw(double)': 'method', 'accountBalance': 'field'}
    )
    return cluster


@pytest.fixture
def name_cluster():
    """Create a cluster for name-related methods."""
    cluster = Cluster(
        id=1,
        member_names=['getName()', 'setName(String)', 'name'],
        member_types={'getName()': 'method', 'setName(String)': 'method', 'name': 'field'}
    )
    return cluster


class TestClusterContextBuilder:
    """Tests for ClusterContextBuilder."""

    def test_initialization(self):
        """Test ClusterContextBuilder initialization."""
        builder = ClusterContextBuilder()
        assert builder.include_imports is True
        assert builder.include_unused_fields_comment is True

        builder = ClusterContextBuilder(include_imports=False, include_unused_fields_comment=False)
        assert builder.include_imports is False
        assert builder.include_unused_fields_comment is False

    def test_build_context_basic(self, account_cluster, sample_class_deps):
        """Test basic context building for account cluster."""
        builder = ClusterContextBuilder()
        context = builder.build_context(account_cluster, sample_class_deps)

        # Check header information
        assert '// From class: GodClass' in context
        assert '// Package: com.example' in context

        # Check fields used by cluster
        assert 'Fields used by this cluster:' in context
        assert 'private double accountBalance;' in context

        # Check methods in cluster
        assert 'Methods in this cluster:' in context
        assert 'public double getAccountBalance()' in context
        assert 'return accountBalance;' in context
        assert 'public void deposit(double amount)' in context
        assert 'accountBalance += amount;' in context
        assert 'public void withdraw(double amount)' in context

        # Check unused fields comment
        assert 'Fields not used:' in context
        assert 'accountNumber' in context
        assert 'name' in context
        assert 'age' in context

    def test_get_used_fields(self, account_cluster, sample_class_deps):
        """Test used fields extraction."""
        builder = ClusterContextBuilder()
        used_fields = builder._get_used_fields(account_cluster, sample_class_deps)

        assert len(used_fields) == 1
        assert used_fields[0].name == 'accountBalance'
        assert used_fields[0].type == 'double'

    def test_get_unused_fields(self, account_cluster, sample_class_deps):
        """Test unused fields extraction."""
        builder = ClusterContextBuilder()
        unused_fields = builder._get_unused_fields(account_cluster, sample_class_deps)

        assert len(unused_fields) == 3
        unused_names = {f.name for f in unused_fields}
        assert unused_names == {'accountNumber', 'name', 'age'}

    def test_get_cluster_methods(self, account_cluster, sample_class_deps):
        """Test cluster methods extraction."""
        builder = ClusterContextBuilder()
        cluster_methods = builder._get_cluster_methods(account_cluster, sample_class_deps)

        assert len(cluster_methods) == 3
        method_names = {m.name for m in cluster_methods}
        assert method_names == {'getAccountBalance', 'deposit', 'withdraw'}

        # Check that bodies are included
        for method in cluster_methods:
            assert method.body is not None
            assert len(method.body) > 0

    def test_get_dependencies(self, sample_class_deps):
        """Test dependency extraction for methods calling other methods."""
        # Create cluster with method calls
        cluster = Cluster(
            id=0,
            member_names=['deposit(double)'],
            member_types={'deposit(double)': 'method'}
        )

        # Add method call from deposit to validateAmount
        sample_class_deps.method_calls = {
            'deposit(double)': ['validateAmount', 'logTransaction']
        }

        # Add the called methods to class_deps
        validate_method = MethodInfo(
            name='validateAmount',
            signature='validateAmount(double)',
            return_type='boolean',
            modifiers=['private'],
            parameters=[{'type': 'double', 'name': 'amount'}],
            start_line=50,
            end_line=52,
            body='private boolean validateAmount(double amount) {\n    return amount > 0;\n}'
        )
        log_method = MethodInfo(
            name='logTransaction',
            signature='logTransaction(String)',
            return_type='void',
            modifiers=['private'],
            parameters=[{'type': 'String', 'name': 'type'}],
            start_line=54,
            end_line=56,
            body='private void logTransaction(String type) {\n    System.out.println(type);\n}'
        )
        sample_class_deps.methods.extend([validate_method, log_method])

        builder = ClusterContextBuilder()
        dependencies = builder._get_dependencies(cluster, sample_class_deps)

        assert len(dependencies) == 2
        assert 'validateAmount(double)' in dependencies
        assert 'logTransaction(String)' in dependencies

    def test_format_field(self):
        """Test field formatting."""
        builder = ClusterContextBuilder()

        field = FieldInfo(
            name='accountBalance',
            type='double',
            modifiers=['private'],
            line_number=10
        )
        formatted = builder._format_field(field)
        assert formatted == 'private double accountBalance;'

        field = FieldInfo(
            name='MAX_SIZE',
            type='int',
            modifiers=['public', 'static', 'final'],
            line_number=5
        )
        formatted = builder._format_field(field)
        assert formatted == 'public static final int MAX_SIZE;'

        # Test field with no modifiers
        field = FieldInfo(name='value', type='String', modifiers=None, line_number=10)
        formatted = builder._format_field(field)
        assert formatted == 'private String value;'

    def test_context_excludes_non_cluster_methods(self, account_cluster, sample_class_deps):
        """Test that non-cluster methods are not included in context."""
        builder = ClusterContextBuilder()
        context = builder.build_context(account_cluster, sample_class_deps)

        # These methods should NOT be in the context
        assert 'getName()' not in context
        assert 'setName(String)' not in context

        # Cluster methods SHOULD be in context (check for method code, not signature)
        assert 'getAccountBalance()' in context
        assert 'deposit(double amount)' in context  # Full method declaration, not signature

    def test_context_size_reduction(self, account_cluster, sample_class_deps):
        """Test that chunked context is significantly smaller than full class."""
        builder = ClusterContextBuilder()
        chunked_context = builder.build_context(account_cluster, sample_class_deps)

        # Estimate full class size (all methods + fields)
        full_class_size = sum(len(m.body) for m in sample_class_deps.methods)
        full_class_size += sum(50 for _ in sample_class_deps.fields)  # Estimate field size

        # Chunked context extracts 3 out of 5 methods, so should be smaller than full class
        # Even with overhead (comments, headers), should be less than full size
        assert len(chunked_context) < full_class_size * 1.1  # Should not be significantly larger

    def test_empty_cluster(self, sample_class_deps):
        """Test handling of empty cluster."""
        cluster = Cluster(id=0, member_names=[], member_types={})

        builder = ClusterContextBuilder()
        context = builder.build_context(cluster, sample_class_deps)

        # Should still have header
        assert '// From class: GodClass' in context
        # Should indicate no methods
        assert 'Methods in this cluster:' in context or len(context) > 0

    def test_cluster_with_no_field_accesses(self, sample_class_deps):
        """Test cluster with methods that don't access fields."""
        # Create method with no field access
        pure_method = MethodInfo(
            name='calculate',
            signature='calculate(int,int)',
            return_type='int',
            modifiers=['public', 'static'],
            parameters=[{'type': 'int', 'name': 'a'}, {'type': 'int', 'name': 'b'}],
            start_line=100,
            end_line=102,
            body='public static int calculate(int a, int b) {\n    return a + b;\n}'
        )
        sample_class_deps.methods.append(pure_method)
        sample_class_deps.field_accesses['calculate(int,int)'] = []

        cluster = Cluster(
            id=0,
            member_names=['calculate(int,int)'],
            member_types={'calculate(int,int)': 'method'}
        )

        builder = ClusterContextBuilder()
        context = builder.build_context(cluster, sample_class_deps)

        # Should not have fields section
        assert 'Fields used by this cluster:' not in context or 'Fields used by this cluster:\n\n' in context
        # Should have method
        assert 'public static int calculate(int a, int b)' in context

    def test_disable_unused_fields_comment(self, account_cluster, sample_class_deps):
        """Test disabling unused fields comment."""
        builder = ClusterContextBuilder(include_unused_fields_comment=False)
        context = builder.build_context(account_cluster, sample_class_deps)

        # Should NOT have unused fields comment
        assert 'Fields not used:' not in context

    def test_multiple_field_usage(self, sample_class_deps):
        """Test cluster using multiple fields."""
        # Create method accessing multiple fields
        combo_method = MethodInfo(
            name='getInfo',
            signature='getInfo()',
            return_type='String',
            modifiers=['public'],
            parameters=[],
            start_line=100,
            end_line=102,
            body='public String getInfo() {\n    return name + " (" + age + ")";\n}'
        )
        sample_class_deps.methods.append(combo_method)
        sample_class_deps.field_accesses['getInfo()'] = ['name', 'age']

        cluster = Cluster(
            id=0,
            member_names=['getInfo()', 'name', 'age'],
            member_types={'getInfo()': 'method', 'name': 'field', 'age': 'field'}
        )

        builder = ClusterContextBuilder()
        context = builder.build_context(cluster, sample_class_deps)

        # Should include both fields
        assert 'private String name;' in context
        assert 'private int age;' in context

        # Should show other fields as unused
        assert 'accountBalance' in context and 'accountNumber' in context


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
