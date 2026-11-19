"""
ARASAKA RELIC // ponto de entrada.

  arasaka-relic          abre a interface
  arasaka-relic --run    faz um backup sem janela (usado pela agenda diária)
"""
import sys


def main() -> int:
    if "--run" in sys.argv[1:]:
        from . import core
        return core.run_cli()
    from .app import main as gui
    return gui(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
