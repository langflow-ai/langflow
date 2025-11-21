class TestComponentNameValidator:
    """Testes para validação de nomes de componentes."""

    def test_invalid_component_name_with_spaces(self):
        """Teste: Nome com espaços deve ser rejeitado."""
        from lfx.utils.component_name_validator import is_valid_component_name

        assert is_valid_component_name("My Component") is False
        assert is_valid_component_name("component name") is False
        assert is_valid_component_name(" component") is False

    def test_invalid_component_name_starting_with_number(self):
        """Teste: Nome começando com número deve ser rejeitado."""
        from lfx.utils.component_name_validator import is_valid_component_name

        assert is_valid_component_name("123component") is False
        assert is_valid_component_name("1MyComponent") is False

    def test_component_name_too_long(self):
        """Teste: Nome com mais de 100 caracteres deve ser rejeitado."""
        from lfx.utils.component_name_validator import is_valid_component_name

        long_name = "a" * 101  # 101 caracteres
        assert is_valid_component_name(long_name) is False

    # Trecho adicionado em test_component_name_validator.py
    def test_component_name_python_keyword(self):
        """Teste: Palavras reservadas do Python devem ser rejeitadas."""
        from lfx.utils.component_name_validator import is_valid_component_name

        assert is_valid_component_name("class") is False
        assert is_valid_component_name("def") is False
        assert is_valid_component_name("import") is False

    def test_component_name_python_builtin(self):
        """Teste: Nomes de funções/tipos built-in do Python devem ser rejeitados."""
        from lfx.utils.component_name_validator import is_valid_component_name

        assert is_valid_component_name("list") is False
        assert is_valid_component_name("str") is False
        assert is_valid_component_name("open") is False
        assert is_valid_component_name("dict") is False
