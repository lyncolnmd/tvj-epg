"""Verify health metadata in inspect JSON or an exported Docker image archive."""
import argparse
import json
import sys
import tarfile


def archive_config(path):
    with tarfile.open(path) as archive:
        manifest_file = archive.extractfile('manifest.json')
        if manifest_file is None:
            raise ValueError('Archive has no Docker manifest')
        manifest = json.load(manifest_file)
        if not manifest:
            raise ValueError('Archive manifest is empty')
        config_file = archive.extractfile(manifest[0]['Config'])
        if config_file is None:
            raise ValueError('Archive has no image config')
        return json.load(config_file).get('config', {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', help='Docker image tar archive to verify')
    args = parser.parse_args()
    try:
        config = archive_config(args.archive) if args.archive else json.load(sys.stdin)[0].get('Config', {})
        healthcheck = config.get('Healthcheck') or {}
        print('Image config Healthcheck:', json.dumps(healthcheck), flush=True)
        expected = ['CMD', 'python', '-m', 'epg.healthcheck']
        if healthcheck.get('Test') != expected:
            raise ValueError('Image config lacks the expected healthcheck; refusing publication')
    except (OSError, ValueError, KeyError, IndexError, tarfile.TarError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print('Image healthcheck verified')
    return 0


if __name__ == '__main__':
    sys.exit(main())
