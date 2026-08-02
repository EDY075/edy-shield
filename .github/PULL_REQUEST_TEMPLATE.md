# Pull Request Template

## Descrição

Por favor, inclua um resumo da mudança e qual problema ela resolve. Inclua motivação e contexto.

Fixes #(issue)

## Tipo de mudança

- [ ] 🐛 Bug fix
- [ ] ✨ Nova feature
- [ ] 📚 Documentação
- [ ] 🔒 Segurança
- [ ] ♻️ Refatoração
- [ ] 🧪 Testes
- [ ] 🚀 Release

## Quality Gates (obrigatório antes de merge)

- [ ] `ruff check .` passa
- [ ] `mypy app --strict` passa (0 issues)
- [ ] `pytest` passa (196+ testes)
- [ ] Cobertura ≥ 90%
- [ ] Testes de segurança negativos passam (se aplicável)
- [ ] Documentação atualizada (se aplicável)
- [ ] ADR atualizado (se mudança arquitetural)

## Checklist

- [ ] Meu código segue o guia de estilo do projeto (`CONTRIBUTING.md`)
- [ ] Adicionei testes que cobrem minha mudança
- [ ] Atualizei a documentação quando necessário
- [ ] Revisei o impacto em segurança (ARES)
- [ ] Não quebrei a API pública (8 símbolos estáveis)

## Evidência

```
# Cole aqui a saída de pytest / mypy / ruff
```

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️