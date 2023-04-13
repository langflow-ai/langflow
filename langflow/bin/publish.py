import argparse
import re
import subprocess

version_pattern = r'\d\.\d\.\d'
parser = argparse.ArgumentParser()
parser.add_argument('version', help='a SEMVER string X.Y.Z')
args = parser.parse_args()
if not re.match(version_pattern, args.version):
    print('argument must be SEMVER string in format X.Y.Z')
else:
    with open('setup.py') as fp:
        old_setupfile = fp.read()
    new_setupfile = re.sub(f"version='{version_pattern}'",
                           f"version='{args.version}'", old_setupfile)
    with open('setup.py', 'w') as fp:
        print(new_setupfile, file=fp)

    subprocess.run(['./publish.sh', 'v' + args.version])
