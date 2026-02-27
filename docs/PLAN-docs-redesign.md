# Plano: Redesign dos Langflow Docs (estilo Langfuse)

## Objetivo
Alinhar a documentação do Langflow ao padrão visual e estrutural do Langfuse, cobrindo tipografia, sidebar, componentes de conteúdo, code blocks, navegação, e experiência geral.

---

## Fase 1: Tipografia e Espaçamento
**Arquivos:** `docs/css/custom.css`

### 1.1 Aumentar tamanhos de heading
- H1: `30px` → `42px` (display, bold, mais impactante como Langfuse)
- H2: `25px` → `30px`
- H3: `22px` → `24px`
- Body: manter `16px`

### 1.2 Ajustar font-weight dos headings
- H1: `font-weight: 700` (bold, display)
- H2: `font-weight: 600` (semibold)
- H3: `font-weight: 600`

### 1.3 Ajustar line-height e spacing
- Headings: `line-height: 1.2` (mais compacto)
- Body: `line-height: 1.7` (mais respiro)
- Margin abaixo de H2: `2rem`
- Margin abaixo de H3: `1.5rem`

### 1.4 Reduzir border-radius global
- `--ifm-global-radius`: `16px` → `10px` (Langfuse usa ~8-12px)

---

## Fase 2: Sidebar Redesign
**Arquivos:** `docs/css/custom.css`, `docs/sidebars.js`, `docs/src/theme/` (novo componente)

### 2.1 Adicionar ícones às categorias de nível 1 da sidebar
- Criar um componente `SidebarCategoryIcon` ou usar HTML items no sidebars.js
- Mapear ícones Lucide para cada seção:
  - Get started → `Rocket`
  - Flows → `Workflow`
  - Agents → `Bot`
  - MCP → `Plug`
  - Develop → `Code`
  - Deploy → `Cloud`
  - Components reference → `Blocks`
  - API reference → `FileCode`
  - Contribute → `GitPullRequest`
  - Support → `HelpCircle`

### 2.2 Estilizar sidebar com separadores de grupo
- Adicionar headers bold (labels de grupo) entre categorias relacionadas
- Grupos sugeridos:
  - **Build** → Get started, Flows, Agents, MCP
  - **Develop** → Develop, Deploy
  - **Reference** → Components reference, API reference
  - **Community** → Contribute, Support

### 2.3 Indicador ativo na sidebar
- Adicionar barra lateral colorida (3px, cor primária) no item ativo
- Estilo: `border-left: 3px solid var(--ifm-color-primary)` com `background` sutil

### 2.4 Ajustar espaçamento da sidebar
- Reduzir padding entre items para visual mais compacto
- Font-size sidebar items: `14px`
- Separador visual entre grupos

---

## Fase 3: Componentes de Conteúdo (novos)
**Arquivos:** `docs/src/components/` (novos componentes)

### 3.1 Criar componente `<Steps>`
- Componente MDX para passos numerados automaticamente
- Estilo: número circular + heading + conteúdo
- Uso:
  ```mdx
  <Steps>
    <Step title="Get API keys">
      Content...
    </Step>
    <Step title="Configure">
      Content...
    </Step>
  </Steps>
  ```
- CSS: counter automático, borda lateral conectando steps

### 3.2 Criar componente `<Card>` e `<Cards>`
- Grid de cards com ícone, título, descrição, e link
- Uso:
  ```mdx
  <Cards cols={2}>
    <Card icon={<Icon name="Eye" />} title="Observability" href="/logging">
      Bullet points aqui
    </Card>
  </Cards>
  ```
- CSS: fundo escuro (dark mode), borda sutil, hover effect, seta →

### 3.3 Criar componente `<Frame>`
- Wrapper de imagem com suporte light/dark automático
- Borda sutil (`ring-1 ring-primary/20`)
- Uso:
  ```mdx
  <Frame>
    <img src="/img/feature.png" />
  </Frame>
  ```
  ou com variantes:
  ```mdx
  <Frame light="/img/feature-light.png" dark="/img/feature-dark.png" />
  ```

### 3.4 Melhorar componente `<Callout>` (admonitions)
- Criar estilo alternativo mais clean (sem borda lateral pesada do Docusaurus)
- Fundo sutil com emoji no lugar do ícone padrão
- Types: `info`, `warning`, `tip`, `note`
- Manter compatibilidade com `:::tip` syntax existente

---

## Fase 4: Code Blocks Aprimorados
**Arquivos:** `docs/css/custom.css`, `docs/docusaurus.config.js`

### 4.1 Adicionar filename labels
- Suporte a `title` nos code blocks do Docusaurus:
  ```md
  ```python title=".env"
  LANGFLOW_API_KEY=your-key
  ```
  ```
- Docusaurus já suporta `title` nativamente - apenas precisamos estilizar melhor
- CSS: fundo diferenciado no header, fonte menor, ícone de arquivo

### 4.2 Adicionar line highlighting
- Docusaurus suporta `{2,4-6}` nativamente via metastring
- Estilizar a linha destacada com fundo sutil (amarelo/primário com 10% opacity)
- CSS para `.theme-code-block-highlighted-line`

### 4.3 Melhorar visual geral dos code blocks
- Border radius: `8px`
- Padding interno mais generoso
- Borda sutil no dark mode

---

## Fase 5: Navegação e UX
**Arquivos:** `docs/src/theme/`, `docs/css/custom.css`, `docs/docusaurus.config.js`

### 5.1 Breadcrumbs mais clean
- Estilizar breadcrumbs para texto simples com `>` separador (como Langfuse)
- Remover fundo/badge do item ativo
- CSS override da classe `.breadcrumbs__link`

### 5.2 Adicionar "Copy page" button (opcional)
- Botão no topo da página que copia o conteúdo markdown
- Implementar como theme wrapper do `DocItem`
- Posição: abaixo do breadcrumb, alinhado à direita

### 5.3 Melhorar Table of Contents (TOC) lateral
- Garantir que a TOC direita esteja visível e estilizada
- Adicionar highlight do item ativo (scroll spy já é nativo)
- Estilizar com font-size menor e cor mais sutil

### 5.4 Navbar fixa (não esconder no scroll)
- Mudar `hideOnScroll: true` → `hideOnScroll: false`
- Navbar sempre visível como no Langfuse

---

## Fase 6: Cards na Homepage e Overview Pages
**Arquivos:** `docs/docs/Get-Started/about-langflow.mdx`, outras páginas de overview

### 6.1 Refatorar a página "About Langflow" com Cards
- Substituir listas de features por `<Cards>` com ícones
- Criar seções visuais para:
  - Prototyping (visual editor, drag-and-drop)
  - Integrations (models, vector stores, tools)
  - Deployment (API, Docker, Kubernetes)

### 6.2 Adicionar "Where to start?" quickstart cards
- 3 cards de entrada rápida:
  - "Build your first flow" → /get-started-quickstart
  - "Explore components" → /concepts-components
  - "Deploy to production" → /deployment-overview

### 6.3 Usar `<Steps>` nos tutoriais e quickstart
- Refatorar `get-started-quickstart.mdx` para usar `<Steps>` em vez de listas numeradas
- Aplicar em outros tutoriais (chat-with-rag, agent, etc.)

---

## Fase 7: Dark Mode Polish
**Arquivos:** `docs/css/custom.css`

### 7.1 Background dark mode
- Mudar de preto puro (`#000`) para cinza muito escuro (`#0a0a0a` ou `#111`)
- Langfuse usa fundo levemente acinzentado, não preto absoluto

### 7.2 Card backgrounds em dark mode
- Cards: fundo `#1a1a1a` com borda `#2a2a2a`
- Hover: borda mais clara ou primária

### 7.3 Code block backgrounds
- Fundo consistente com o tema (não preto puro)
- Borda sutil em dark mode

---

## Fase 8: Vídeos e Mídia
**Arquivos:** `docs/src/components/` (novo componente)

### 8.1 Criar componente `<Video>`
- Wrapper com aspect ratio 16:9
- Suporte a YouTube, Loom, e MP4 local
- Usa `react-player` (já é dependência)
- Uso:
  ```mdx
  <Video src="https://youtube.com/..." />
  ```

---

## Ordem de Implementação Recomendada

| Prioridade | Fase | Impacto | Esforço |
|---|---|---|---|
| 1 | Fase 1: Tipografia | Alto | Baixo |
| 2 | Fase 4: Code Blocks | Alto | Baixo |
| 3 | Fase 5: Navegação/UX | Alto | Médio |
| 4 | Fase 7: Dark Mode | Médio | Baixo |
| 5 | Fase 3: Componentes | Alto | Alto |
| 6 | Fase 2: Sidebar | Alto | Alto |
| 7 | Fase 6: Homepage/Cards | Médio | Médio |
| 8 | Fase 8: Vídeos | Baixo | Baixo |

---

## Arquivos Principais Afetados

| Arquivo | Tipo de mudança |
|---|---|
| `docs/css/custom.css` | Edição extensiva (tipografia, cores, spacing, dark mode) |
| `docs/docusaurus.config.js` | Edição (navbar, code block config) |
| `docs/sidebars.js` | Edição (ícones, grupos) |
| `docs/tailwind.config.js` | Edição (design tokens customizados) |
| `docs/src/components/Steps.tsx` | **Novo** |
| `docs/src/components/Card.tsx` | **Novo** |
| `docs/src/components/Cards.tsx` | **Novo** |
| `docs/src/components/Frame.tsx` | **Novo** |
| `docs/src/components/Video.tsx` | **Novo** |
| `docs/src/components/Callout.tsx` | **Novo** |
| `docs/src/theme/DocItem/` | **Novo** (copy page button) |
| `docs/docs/Get-Started/about-langflow.mdx` | Edição (refatorar com Cards) |
| `docs/docs/Get-Started/get-started-quickstart.mdx` | Edição (refatorar com Steps) |

---

## Notas

- Todas as mudanças são backward-compatible - o conteúdo `.mdx` existente continua funcionando
- Novos componentes são opcionais - páginas existentes podem ser migradas gradualmente
- A Fase 1 (tipografia) e Fase 4 (code blocks) podem ser feitas imediatamente com mudanças apenas no CSS
- As Fases 3 e 6 requerem criação de componentes React + migração de conteúdo MDX
