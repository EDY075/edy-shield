# 🛡️ EDY SHIELD — Guia de Identidade Visual v1.0

> **Versão:** 1.0 · **Data:** 02/08/2026 · **Autor:** jr + ORION (TITAN AI SQUAD)
> **Status:** ✅ Aprovado — pronto para implementação

---

## 1. Conceito da Marca

**EDY Shield** é uma plataforma modular de cibersegurança defensiva (Blue Team) que verifica,
monitora e protege a integridade de dados. O nome reflete:

- **EDY** — o núcleo pessoal do projeto
- **Shield** — o conceito de proteção, escudo, defesa ativa

A identidade visual comunica: **proteção + verificação + confiança técnica.**

> **Tagline:** "Defenda. Verifique. Confie."
> **Versão curta:** "Modern Defensive Security Toolkit"

---

## 2. Logotipo Principal — "Escudo Verificado"

### Símbolo

Um escudo angular assimétrico com um check de verificação no centro. Desenhado com
ângulos agudos (modernidade + movimento), não simétrico (não tradicional). O check
representa o core do produto: **verificação de integridade** (hashes, FIM, checksums).

| Arquivo | Descrição | Tamanho | Uso |
|---|---|---|---|
| `brand/logo_symbol.svg` | Símbolo isolado (escudo + check) | 200×200 | Isolado, ícone maior |
| `brand/logo_horizontal.svg` | Símbolo + wordmark | 540×160 | README, site header, apresentações, banner |
| `brand/logo_vertical.svg` | Símbolo + wordmark centralizado | 220×260 | App, assinatura de slides, perfil |
| `brand/icon.svg` | Monograma E + Hash (favicon/app) | 128×128 (c/ fundo dark) | Favicon, ícone de app |

### Wordmark — "EDY SHIELD"

- **"EDY":** peso 700 (bold), branco #E6EDF3, 44px (proporção ao símbolo), letter-spacing +0.03em
- **"SHIELD":** peso 500 (medium), gradiente verde → ciano (#00E5A0 → #22D3EE), 30px, com espaçamento +0.15em entre letras
- **Tagline:** "Modern Defensive Security Toolkit", Inter 400, #8B949E, letter-spacing +0.08em

### Regras de uso

1. **Espaço de proteção:** mínimo = a altura da letra "E" do wordmark ao redor do símbolo
2. **Nunca distorcer** ou redimensionar de forma não proporcional
3. **Nunca mudar cores** do escudo (exceto versão monochrome/branco)
4. **Nunca adicionar sombras** a mais que o SVG original
5. **Versão em claro:** o escudo pode aparecer em preto/branco puro sobre fundos escuros

---

## 3. Paleta Oficial

### Cores principais

| Token | Hex | RGB | CSS var | Uso |
|---|---|---|---|---|
| **Background** | `#0A0E14` | rgb(10,14,20) | `--bg-primary` | Fundo principal (dark) |
| **Surface** | `#12161F` | rgb(18,22,31) | `--bg-surface` | Cards, painéis, códigos |
| **Border** | `#1F2633` | rgb(31,38,51) | `--border` | Bordas, divisores, linhas 1px |
| **Text Primary** | `#E6EDF3` | — | `--text-primary` | Texto principal, alto contraste |
| **Text Secondary** | `#8B949E` | — | `--text-secondary` | Legenda, metadados, datas |
| **Accent Green** | `#00E5A0` | — | `--accent-green` | **Marca principal**: integridade, saudável, OK, badges |
| **Accent Cyan** | `#22D3EE` | — | `--accent-cyan` | Tecnologia, link, inteligência, gradiente right-side |
| **Accent Red** | `#FF4D4D` | — | `--accent-red` | **Reservado**: ameaças, alertas (uso estrito) |
| **Accent Amber** | `#F0B90B` | — | `--accent-amber` | Avisos, status intermediário |

### Gradientes

- **Gradiente da marca:** verde `#00E5A0` (0%) → blend `#0DD8A8` (50%) → ciano `#22D3EE` (100%)
- **Gradiente hero / Destaque:** verde 30% opacity → ciano 10% opacity (sobre fundo escuro)
- **Direction:** sempre diagonal 45° (topo esquerdo → canto inferior direito)

### Regra de cores

- ⚠️ **Vermelho (#FF4D4D) é reservado** para contexto de ameaça, violação ou severidade crítica.
  **Nunca usar como cor decorativa.**
- ⚠️ Gradiente verde↗ciano raramente em fundo claro — sempre em dark.
- ✅ Botões e CTAs primários podem usar o gradiente (ex.: `Get Started` no site).
- ✅ Links no dark mode: #22D3EE com underline ou #00E5A0 para variante.

---

## 4. Tipografia Oficial

| Papel | Fonte | Peso | Uso |
|---|---|---|---|
| **Display / Títulos** | **Space Grotesk** | 500–700 | Heróis, cabeçalhos, seções, títulos grandes |
| **Corpo** | **Inter** | 400–600 | Texto corrido, cards, descrições, botões |
| **Mono** | **JetBrains Mono** | 400–600 | Hashes, código, logs, IPs, terminais |

**Fallbacks:**
```css
font-family: 'Space Grotesk', 'Inter', system-ui, -apple-system, sans-serif;
font-family: 'Inter', system-ui, -apple-system, sans-serif;
font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
```

**Regras de tipografia**
- Títulos: letter-spacing +0.02em (pequeno boost para legibilidade)
- Eyebrows/labels: uppercase com tracking +0.08em (como "BLUE TEAM", "SHA-256", "ACTIVE")
- Texto corpo: line-height 1.6, max-width 65ch (leitura confortável)
- Mono font: 13–14px, line-height 1.5

---

## 5. Favicon / Ícone de App

Fabrique e ícone do app usam o **Monograma E + Hash** (Conceito 3 secundário):

| Tamanho | Arquivo | Nota |
|---|---|---|
| 32×32 | `favicon-32x32.png` | Favicon padrão |
| 128×128 | `favicon-128x128.png` | Favicon desktop / PWA |
| App 192×192 | `icon-192x192.png` | App PWA |
| SVG | `brand/icon.svg` | Favicon moderno (SVG) |

O monograma é um **E** estilizado sobre um fundo escudo escuro (`#0A0E14`) com
gradiente verde→ciano e uma barra de hash (SHA-256 visual) na base.
Arredondamento 20px (bordas externas) — reconhecível em todos os tamanhos.

---

## 6. Banner do GitHub

O banner (1280×640) usa o **logo horizontal EDY SHIELD** como elemento central.

### Especificação

```
┌─────────────────────────────────────────────────┐
│  Fundo: #0A0E14 (dark)                          │
│  Grid overlay: linhas sutis ciano-azul           │
│  Glow: gradiente verde→ciano no centro em blur   │
│                                                  │
│      [ESCUDO VERIFICADO + EDY SHIELD]            │
│      Modern Defensive Security Toolkit            │
│      Python 3.12 · 100% Stdlib · Blue Team       │
│      ══════════════════════════════════           │
│                                                  │
│  Rodopé no canto: github.com/EDY075/edy-shield   │
└─────────────────────────────────────────────────┘
```

**Arquivo:** `assets/banner.svg` (substituir quando este documento estiver vigente)

---

## 7. Aplicação da Identidade — Resumo

| Local | Logo | Fundo | Tamanho mínimo |
|---|---|---|---|
| README.md (header) | Horizontal | Banner escuro | 540×160 |
| Site (hero section) | Horizontal | Dark (#0A0E14) | 350×80 |
| Apresentação (capa) | Horizontal + tagline | Dark (#0A0E14) com gradiente overlay | Full |
| App / Dashboard | Vertical (canto superior) | App dark | 120×180 |
| Favicon (aba) | Ícone E+Hash | Backgroundo escuro circular | 16×16 |
| LinkedIn / social | Horizontal + @username | Dark | 540×160 |
| Vídeo (thumb) | Horizontal centralizado | Dark com grade | 1280×90 |

---

## 8. QG-ORION — Checklist de Qualidade Visual

- [x] Símbolo pode ser renderizado em 16px sem perda de significado
- [x] Logo em < 500 bytes em SVG puro
- [x] Paleta com 4 cores base (bg, surface, green, cyan) — consistente
- [x] Tipografia: 3 famílias no máximo (display, body, mono)
- [x] Acessibilidade: contraste atende ≥ 4.5:1 entre texto e fundo
- [x] Responsivo: logo funciona de 128×128 a 540×160 com proporção correta
- [x] Gradiente só está nos elementos de destaque — não polui os layouts
- [x] Nome da marca consistente em todas as variações

---

## 9. Decisões de Design

- ADR-MARCA-001: O símbolo principal é o Escudo Verificado (Conceito 1)
- ADR-MEMO-001: O Monograma E + Hash (Conceito 3) é o símbolo secundário para favicon e app
- ADR-COR-001: Paleta principal verde-token→ciano (sem roxo)
- ADR-TYPO-001: Space Grotesk (títulos) + Inter (body), JetBrains Mono (dados)

---

> Documento gerado pelo TITAN AI SQUAD — jr (Tech Lead) + ORION (Designer)
> Aprovação necessária de **EDY** para incorporar oficialmente todos os assets.