# import相关的库
# %matplotlib inline
# from IPython import get_ipython
# get_ipython().run_line_magic('matplotlib', 'inline')
'exec(%matplotlib inline)'
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 数据读入用pd.read_csv()
data_01 = pd.read_csv('D:/tianchi/datalab/data_01.csv')
data_02 = pd.read_csv('D:/tianchi/datalab/data_02.csv')
data_03 = pd.read_csv('D:/tianchi/datalab/data_03.csv')
# 数据合并
data = pd.concat([data_01, data_02, data_03])
# 察看前5行数据
data.head()
# print(data.head())

# 查看数据的信息，包括每个字段的名称，非空数量，字段的数据类型
data.info()
# print(data.info())

# 用统计学指标快速描述数据的概要
data.describe()
# print(data.describe())
# 以上都属于数据载入和总览

# 缺失值处理
# 从data.info()得知，contbr_employer,contbr_occupation均有少量缺失，均填充为NOT PROVIDED
data['contbr_employer'].fillna('NOT PROVIDED', inplace=True)
data['contbr_occupation'].fillna('NOT PROVIDED', inplace=True)
# print(data.info())    //验证填充

# 数据转换，利用字典映射进行转换：党派分析
# 美国大选一般是民主党和共和党之争，虽然数据中没有党派这个字段，但是通过候选人名称即cand_nm,
# 可以得到对应的党派信息

# 查看数据种总统候选人都有谁
print('共有{}位候选人，分别是'.format(len(data['cand_nm'].unique())))
data['cand_nm'].unique()
# print(data['cand_nm'].unique())

# 通过搜索引擎等途径，获取到每个总统候选人的所属党派，建立字典parties，候选人名字作为键， 所属党派作为对应的值
parties = {'Bachmann, Michelle': 'Republican',
           'Cain, Herman': 'Republican',
           'Gingrich, Newt': 'Republican',
           'Huntsman, Jon': 'Republican',
           'Johnson, Gary Earl': 'Republican',
           'McCotter, Thaddeus G': 'Republican',
           'Obama, Barack': 'Democrat',
           'Paul, Ron': 'Republican',
           'Pawlenty, Timothy': 'Republican',
           'Perry, Rick': 'Republican',
           "Roemer, Charles E. 'Buddy' III": 'Republican',
           'Romney, Mitt': 'Republican',
           'Santorum, Rick': 'Republican'}
# 增加一列party存储党派信息
# 通过map映射函数， 增加一列party存储党派信息
data['party'] = data['cand_nm'].map(parties)
# 查看两个党派的情况
data['party'].value_counts()
# print(data['party'].value_counts())
# 共和党（Republican）的赞助总金额更高，民主党获得的赞助次数更多一些

# 排序：按照职业汇总对赞助总金额进行排序，展示前20项， False为降序
data.groupby('contbr_occupation')['contb_receipt_amt'].sum().sort_values(ascending=False)[:20]
# print(data.groupby('contbr_occupation')['contb_receipt_amt'].sum().sort_values(ascending=False)[:20])

# 利用函数进行数据转换， 职业与雇主信息分析，dict.get允许没有映射关系的职业也能“通过”
# 建立一个职业对应字典，把相同职业的不同表达映射为对应的职业，比如把C.E.O映射为CEO
occupation_map = {
  'INFORMATION REQUESTED PER BEST EFFORTS':'NOT PROVIDED',
  'INFORMATION REQUESTED':'NOT PROVIDED',
  'SELF' : 'SELF-EMPLOYED',
  'SELF EMPLOYED' : 'SELF-EMPLOYED',
  'C.E.O.':'CEO',
  'LAWYER':'ATTORNEY',
}

# 如果不在字典中，返回x
f = lambda x: occupation_map.get(x, x)
data.contbr_occupation = data.contbr_occupation.map(f)

# 同样的，对雇主信息进行类似转换
emp_mapping = {
   'INFORMATION REQUESTED PER BEST EFFORTS' : 'NOT PROVIDED',
   'INFORMATION REQUESTED' : 'NOT PROVIDED',
   'SELF' : 'SELF-EMPLOYED',
   'SELF EMPLOYED' : 'SELF-EMPLOYED',
}
f = lambda x: emp_mapping.get(x, x)
data.contbr_employer = data.contbr_employer.map(f)

# 数据筛选
# 赞助金额筛选， 限定数据集只有正出资额
data = data[data['contb_receipt_amt']>0]
# 候选人筛选（Obama, Romney）
# 查看各候选人获得的赞助总金额
data.groupby('cand_nm')['contb_receipt_amt'].sum().sort_values(ascending=False)
# print(data.groupby('cand_nm')['contb_receipt_amt'].sum().sort_values(ascending=False))
# 赞助基本集中在Obama、Romney之间，为了更好的聚焦在两者间的竞争，我们选取这两位候选人的数据子集作进一步分析
# 选取候选人为Obama, Romney的子集数据
data_vs = data[data['cand_nm'].isin(['Obama, Barack', 'Romney, Mitt'])].copy()

# 面元化数据
# 接下来我们对该数据做另一种非常实用的分析，利用cut函数根据出资额大小将数据离散化到多个面元中
bins = np.array([0, 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000])
labels = pd.cut(data_vs['contb_receipt_amt'], bins)
# print(labels)

# 数据聚合与分组运算
# 分组计算Grouping，分组运算是一个“split-apply-combine”的过程
# 透视表(pivot_table)分析党派和职业
# 按照党派，职业对赞助金额进行汇总，类似excel中的透视表操作，聚合函数为sum
by_occupation = data.pivot_table('contb_receipt_amt', index='contbr_occupation', columns='party',aggfunc='sum')
# 过滤掉赞助金额小于200W的数据
over_2mm = by_occupation[by_occupation.sum(1)>2000000]
# print(over_2mm)
over_2mm.plot(kind='bar')

# 分组级运算和转换:根据职业与雇主信息分组运算
# 由于职业和雇主的处理非常相似，我们定义函数get_top_amounts()对两个字段进行分析处理
def get_top_amounts(group, key, n=5):
# 传入groupby分组后的对象，返回按照key字段汇总的排序前n的数据
    totals = group.groupby(key)['contb_receipt_amt'].sum()
    return totals.sort_values(ascending=False)[:n]

grouped = data_vs.groupby('cand_nm')
grouped.apply(get_top_amounts, 'contbr_occupation', n=7)

# 使用同样的函数对雇主进行分析处理
grouped.apply(get_top_amounts, 'contbr_employer', n=10)

# 对赞助金额进行分组分析（matplotlib画图）
# labels是之前赞助金额离散化的series
grouped_bins = data_vs.groupby(['cand_nm', labels])
grouped_bins.size().unstack(0)
# 再统计各区间的赞助金额
bucket_sums=grouped_bins['contb_receipt_amt'].sum().unstack(0)
# print(bucket_sums)

# Obama, Romney各区间赞助总金额
bucket_sums.plot(kind='bar')

# 算出每个区间两位候选人收到赞助总金额的占比
normed_sums = bucket_sums.div(bucket_sums.sum(axis=1), axis=0)
# print(normed_sums)

# 使用柱状图，指定stacked=True进行堆叠，即可完成百分比堆积图
normed_sums[:-2].plot(kind='bar', stacked=True)

# 按照赞助人姓名分组计数，计算重复赞助次数最多的前20人
data.groupby('contbr_nm')['contbr_nm'].count().sort_values(ascending=False)[:20]


# 时间处理:to_datetime方法解析多种不同的日期表示形式
data_vs['time'] = pd.to_datetime(data_vs['contb_receipt_dt'])

# 以时间作为索引
data_vs.set_index('time', inplace=True)
# print(data_vs.head())

# 重采样和频度转换
vs_time = data_vs.groupby('cand_nm').resample('M')['cand_nm'].count()
vs_time.unstack(0)

# 用面积图把11年4月-12年4月两位总统候选人接受的赞助笔数做个对比可以看出，
# 越临近竞选，大家赞助的热情越高涨，奥巴马在各个时段都占据绝对的优势
fig1, ax1 = plt.subplots(figsize=(32, 8))
vs_time.unstack(0).plot(kind='area', ax=ax1, alpha=0.6)
plt.show()





