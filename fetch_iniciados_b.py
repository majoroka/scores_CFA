from competition_configs import INICIADOS_B
from competition_sync import run_sync

OUTPUT_FILE = 'data/iniciados-b.json'


def main():
    run_sync(INICIADOS_B)


if __name__ == '__main__':
    main()
