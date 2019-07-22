# 注意文件名不能命名为pandas，不然会报series错误
import numpy as np, pandas as pd

'''
arr1 = np.arange(10)
# print(arr1)
# print(type(arr1))
s1 = pd.Series(arr1)
# print(s1)
# print(type(s1))
dic1 = {'a': 10, 'b': 20, 'c': 30, 'd': 40, 'e': 50}
# print(dic1)
# print(type(dic1))
arr2 = np.array(np.arange(12).reshape(4, 3))
# print(arr2)
# print(type(arr2))
df1 = pd.DataFrame(arr2)
print(df1)
print(type(df1))
'''
dic2 = {'a': [1, 2, 3, 4], 'b': [5, 6, 7, 8], 'c': [9, 10, 11, 12], 'd': [13, 14, 15, 16]}
# print(dic2)
# print(type(dic2))
df2 = pd.DataFrame(dic2)
print(df2)
print(type(df2))

