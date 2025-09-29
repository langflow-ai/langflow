# Universal Output Selector Component

Um componente poderoso que permite selecionar e acessar o valor de qualquer output de qualquer componente no flow através de uma interface dropdown dinâmica.

## Funcionalidades

### 🔍 **Descoberta Automática**
- Escaneia automaticamente todos os componentes no flow
- Identifica todos os outputs disponíveis
- Atualiza dinamicamente quando componentes são adicionados/removidos

### 📋 **Interface Intuitiva**  
- Dropdown com nomes dos componentes e tipos de outputs
- Formato: `Nome do Componente → Nome do Output (Tipos)`
- Botão de refresh para atualizar a lista
- Atualização em tempo real

### 🎯 **Seleção Flexível**
- Escolha qualquer output de qualquer componente
- Filtragem por tipos de output (opcional)
- Opção de incluir/excluir o próprio componente

### 📊 **Informações Detalhadas**
- Metadados sobre o output selecionado
- Status de execução do componente
- Lista completa de outputs disponíveis

## Inputs

### `selected_output` (Dropdown)
- **Descrição**: Escolha qualquer output de qualquer componente no flow
- **Formato**: `component_id::output_name`
- **Atualização**: Dinâmica com botão de refresh

### `include_self` (Boolean - Avançado)
- **Descrição**: Se deve incluir outputs deste próprio componente
- **Padrão**: `false`

### `filter_types` (String - Avançado)  
- **Descrição**: Lista separada por vírgulas de tipos para filtrar
- **Exemplo**: `"Message,Data"` (deixe vazio para todos os tipos)

## Outputs

### `selected_value`
- **Tipo**: `Any`
- **Descrição**: O valor atual do output selecionado
- **Comportamento**:
  - Retorna o valor se o componente foi executado
  - Retorna aviso se o componente ainda não foi executado
  - Retorna erro se a seleção for inválida

### `output_info` 
- **Tipo**: `Data`
- **Descrição**: Informações detalhadas sobre o output selecionado
- **Conteúdo**:
  ```json
  {
    "component_id": "ChatInput-ABC123",
    "component_display_name": "Chat Input",
    "output_name": "message",
    "output_info": {
      "name": "message",
      "types": ["Message"],
      "method": "build_message"
    },
    "has_been_executed": true,
    "available_results": ["message"]
  }
  ```

### `available_outputs`
- **Tipo**: `Data` 
- **Descrição**: Lista completa de todos os outputs disponíveis no flow
- **Formato**:
  ```json
  {
    "total_outputs": 15,
    "outputs": [
      {
        "component_id": "ChatInput-ABC123",
        "component_display_name": "Chat Input", 
        "output_name": "message",
        "output_types": ["Message"],
        "selector_value": "ChatInput-ABC123::message"
      }
    ]
  }
  ```

## Casos de Uso

### 1. **Debug e Inspeção**
```python
# Use o Universal Output Selector para inspecionar valores
# de qualquer componente durante o desenvolvimento
```

### 2. **Roteamento Dinâmico**
```python
# Selecione diferentes outputs baseado em condições
# para criar flows adaptativos
```

### 3. **Aggregação de Dados**
```python
# Combine dados de múltiplos componentes
# selecionando seus outputs individualmente
```

### 4. **Análise de Flow**
```python
# Use available_outputs para entender
# a estrutura completa do seu flow
```

## Implementação Técnica

### Descoberta de Outputs
```python
def _discover_available_outputs(self) -> list[tuple[str, str, list[str]]]:
    # Acessa self.graph.vertex_map para enumerar todos os componentes
    # Extrai informações de outputs de cada vertex
    # Aplica filtros de tipo se especificados
```

### Acesso aos Valores
```python
def get_selected_value(self) -> Any:
    # Parse da seleção: "component_id::output_name"
    # Acessa target_vertex.results[output_name]
    # Retorna o valor atual ou status/erro apropriado
```

### Atualização Dinâmica
```python
def update_build_config(self, build_config: dict, field_name: str, field_value: Any) -> dict:
    # Chamado automaticamente quando o dropdown é refreshed
    # Redescobre outputs e atualiza opções disponíveis
    # Mantém seleção atual se ainda válida
```

## Exemplo de Flow

1. **Adicione componentes** ao seu flow (ChatInput, LLM, etc.)
2. **Adicione Universal Output Selector** da categoria Helpers
3. **Clique no botão refresh** no dropdown "Select Output"
4. **Escolha qualquer output** da lista
5. **Use os outputs** do selector em outros componentes

## Vantagens

- ✅ **Zero configuração**: Funciona automaticamente
- ✅ **Detecção automática**: Encontra todos os outputs
- ✅ **Interface amigável**: Dropdown com nomes legíveis  
- ✅ **Atualização dinâmica**: Sempre sincronizado
- ✅ **Informações ricas**: Metadados completos
- ✅ **Flexível**: Suporta qualquer tipo de output
- ✅ **Robusto**: Trata estados e erros graciosamente

## Limitações

- ⚠️ Só pode acessar valores **após** a execução dos componentes
- ⚠️ Requer que o flow esteja **construído** para descobrir outputs
- ⚠️ A lista de outputs é **estática** até o próximo refresh

## Localização

- **Arquivo**: `src/backend/base/langflow/components/helpers/universal_output_selector.py`
- **Categoria**: Helpers
- **Classe**: `UniversalOutputSelectorComponent`