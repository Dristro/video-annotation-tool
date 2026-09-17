"""Video Annotation Tool (import name `vat`).

`__version__` is the single source of truth for the app's version:
pyproject.toml reads it dynamically (`[tool.setuptools.dynamic]`), the
`.app` bundle's Info.plist is stamped with it by `packaging/vat.spec`,
and `vat --version` prints it. It's a plain attribute rather than an
`importlib.metadata` lookup so it also works inside a PyInstaller bundle,
where the package's dist-info isn't necessarily collected.
"""

__version__ = "1.0.0"
