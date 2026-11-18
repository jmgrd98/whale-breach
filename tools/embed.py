import json, os
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'film')
src = open(os.path.join(root, 'whale_breach.py')).read()
open(os.path.join(root, 'script.js'), 'w').write('window.WHALE_SRC = ' + json.dumps(src) + ';\n')
print(len(src.rstrip().split('\n')), 'lines embedded')
