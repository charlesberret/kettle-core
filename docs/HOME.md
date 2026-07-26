# Kettle project family

Kettle is one product with independently released repositories.

**Product home and star target:**
[github.com/charlesberret/kettle](https://github.com/charlesberret/kettle)

| Repository | Role |
|---|---|
| [`kettle`](https://github.com/charlesberret/kettle) | Product story, public roadmap, and family navigation |
| [`kettle-core`](https://github.com/charlesberret/kettle-core) | Desk format, API, runtime, CLI, kits, and reference web UI |
| [`kettle-vscode`](https://github.com/charlesberret/kettle-vscode) | VS Code and Cursor adapter |
| [`kettle-desktop`](https://github.com/charlesberret/kettle-desktop) | macOS Electron shell over the core web UI |

The core is the single authority for product semantics. Adapters attach to its
localhost API and declare the contract versions they support. They do not fork
the desk, its migrations, or the reference web interface.

Kettle was previously named Setsweep. Old command names, Desk paths, and
process identity are accepted only as documented compatibility surfaces. New
copy and new state use Kettle.

See [REPOSITORIES.md](./REPOSITORIES.md) for ownership and compatibility.
