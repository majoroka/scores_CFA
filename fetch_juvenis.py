from competition_configs import JUVENIS
from competition_sync import run_sync

OUTPUT_FILE = 'data/juvenis.json'


def main():
    run_sync(JUVENIS)


if __name__ == '__main__':
    main()
