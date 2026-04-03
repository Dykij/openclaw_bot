# Knowledge Store Data

YAML files in this directory are loaded at startup by the Knowledge Store.

## Format
```yaml
category: "python"
version: "3.14"
facts:
  - "Pattern matching is fully supported"
  - "GIL removed in free-threaded mode"
sources:
  - "https://docs.python.org/3.14/whatsnew/3.14.html"
```

Place `.yaml` files here to extend the bot's knowledge base.
