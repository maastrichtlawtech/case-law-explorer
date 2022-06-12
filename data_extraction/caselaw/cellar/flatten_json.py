import json
from os.path import dirname, abspath, basename, join
from os import getenv
import sys
import pandas as pd
import re 

sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))

from definitions.storage_handler import CELLAR_DIR, Storage

file_path = join(CELLAR_DIR + "/ECLI:EU:C:2010:126" + ".json")

#print(file_path)

data = ''

with open(file_path,'r') as f:
	data = json.loads(f.read())

for x in data:
	print(x)
	


# #print(df.to_string())

# def flatten_json(y):
#     out = {}

#     def flatten(x, name=''):
#         if type(x) is dict:
#             for a in x:
#                 flatten(x[a], name + a + '_')
#         elif type(x) is list:
#             i = 0
#             for a in x:
#                 flatten(a, name + str(i) + '_')
#                 i += 1
#         else:
#             out[name[:-1]] = x

#     flatten(y)
#     return out

# df = flatten_json(data)
# df = pd.json_normalize(df)
# print(df)