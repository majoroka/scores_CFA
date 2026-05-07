from competition_configs import INFANTIS_B
from competition_sync import run_sync

OUTPUT_FILE = 'data/infantis-b.json'


def main():
    run_sync(INFANTIS_B)


if __name__ == '__main__':
    main()
