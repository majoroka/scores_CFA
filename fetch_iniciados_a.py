from competition_configs import INICIADOS_A
from competition_sync import run_sync

OUTPUT_FILE = 'data/iniciados-a.json'


def main():
    run_sync(INICIADOS_A)


if __name__ == '__main__':
    main()
