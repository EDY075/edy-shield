"""Interface web do EDY Shield (Sprint 3, Missão 9).

A UI é dividida em:

* :mod:`app.ui.server` — servidor HTTP (stdlib) que expõe a API REST e
  serve os assets estáticos. Consome os plugins exclusivamente via
  :class:`PluginManager` — nenhuma lógica de negócio vive na interface.
* ``static/`` — front-end (HTML/CSS/JS) que faz ``fetch`` para a API.
"""
