# 参考来源：https://blog.csdn.net/weixin_42001089/article/details/85013073
# 参考来源：https://github.com/Mryangkaitong/python-Machine-learning/blob/master/Xgboost/code/ofoFeature.ipynb

# 以 csv 类型的文件中导入数据,可以快速地对数据进行复杂的转换和过滤等操作
import pandas as pd
# 支持高维度数组和矩阵运算
import numpy as np
# 格式化操作日期和时间的类
from datetime import date
import datetime as dt
# 与操作系统有关的操作
import os

#xgboost模型训练阶段用到的了
import pickle   # pickle用来保存训练好的模型
import xgboost as xgb
from sklearn.preprocessing import MinMaxScaler      # 将属性值缩放到指定的范围之间
from sklearn.metrics import log_loss, roc_auc_score, auc, roc_curve
from sklearn.model_selection import train_test_split    # 随机划分训练集和测试集,交叉验证中常用的函数

# 这句用来解决SettingWithCopyWarning问题，来自stackoverflow
pd.options.mode.chained_assignment = None

# 源数据存储路径
OriginPath = 'D:/tianchi/O2O/O2O_data'
# 进行特征分析后数据的存储路径
ProcessedPath = 'D:/tianchi/O2O/O2O_data'

# off_train:线下数据的训练集,off_test:线下数据的测试集
off_train = pd.read_csv(os.path.join(OriginPath, 'ccf_offline_stage1_train.csv'),
                        header=0, keep_default_na=False)
# header指定了第0行作为列名，keep_default_na可以改参数，数据中有缺省值的默认为null，而不是NAN，方便判断
off_train.columns = ['user_id', 'merchant_id', 'coupon_id', 'discount_rate', 'distance', 'date_received', 'date']

off_test = pd.read_csv(os.path.join(ProcessedPath, 'ccf_offline_stage1_test_revised.csv'),
                       header=0, keep_default_na=False)
# 测试集test相比于训练集而言少了消费优惠卷的日期
off_test.columns = ['user_id', 'merchant_id', 'coupon_id', 'discount_rate', 'distance', 'date_received']

# 检查数据读入情况
# print(off_train.info())     # 数据总览
# print(off_train.head(5))    # 显示前5行信息
# print(off_test.head(5))

# 一般时间类的分析都按滑窗法划分数据集, 数据划分和特征提取及其重要
# 交叉训练集一：收到卷的日期大于4月14日并且小于5月14日(提取label)
dataset1 = off_train[(off_train.date_received >= '20160414') & (off_train.date_received <= '20160514')]
# 交叉训练集一特征：线下数据中领卷和用卷日子大于1月1日并且小于4月13日(提取feature)
feature1 = off_train[((off_train.date >= '20160101') & (off_train.date <= '20160413')) |
                     ((off_train.date == 'null') & (off_train.date_received >= '20160101') &
                      (off_train.date_received <= '20160413'))]

# 交叉训练集二：日期大于5月15日和小于6月15日
dataset2 = off_train[(off_train.date_received >= '20160515') & (off_train.date_received <= '20160615')]
# 交叉训练集二特征：日期大于2月1日和小于5月14日
feature2 = off_train[((off_train.date >= '20160201') & (off_train.date <= '20160514')) |
                     ((off_train.date == 'null') & (off_train.date_received >= '20160201') &
                      (off_train.date_received <= '20160514'))]

# 测试集(利用的7月的特征，实际不可能)
dataset3 = off_test
# 测试集特征：日期大于3.15和小于6.15
feature3 = off_train[((off_train.date >= '20160315') & (off_train.date <= '20160630')) |
                     ((off_train.date == 'null') & (off_train.date_received >= '20160315') &
                      (off_train.date_received <= '20160630'))]


def get_user_date_datereceived_gap(s):  # 计算领取优惠卷的时间间隔
    s = s.split(':')
    return (date(int(s[0][0:4]), int(s[0][4:6]), int(s[0][6:8])) - date(int(s[1][0:4]), int(s[1][4:6]),
                                                                        int(s[1][6:8]))).days


def GetUserRelatedFeature(feature): # 用户相关的特征提取

    user = feature[['user_id', 'merchant_id', 'coupon_id', 'discount_rate', 'distance', 'date_received', 'date']].copy()
    t = user[['user_id']].copy()
    t.drop_duplicates(inplace=True) # 摒弃掉重复的user_id,inplace为true表示对t的直接操作

    # 用户一共买的商品
    t1 = user[user.date != 'null'][['user_id', 'merchant_id']].copy()
    t1.drop_duplicates(inplace=True)
    t1.merchant_id = 1  # 方便下一句对所有消费的商家求和
    # groupby进行聚合和分组运算，sum内部求同一个user的所有商家的和，reset_index还原索引，避免一些逻辑错误
    t1 = t1.groupby('user_id').agg('sum').reset_index()  # 使数据规整
    t1.rename(columns={'merchant_id': 'count_merchant'}, inplace=True)

    # 客户使用优惠券线下购买距离商店的最小距离
    # t2是距离相关的的公共数据
    t2 = user[(user.date != 'null') & (user.coupon_id != 'null')][['user_id', 'distance']]
    t2.replace('null', -1, inplace=True)
    t2.distance = t2.distance.astype('int')     # 类型转换
    t2.replace(-1, np.nan, inplace=True)
    # 最小距离
    t3 = t2.groupby('user_id').agg('min').reset_index()
    t3.rename(columns={'distance': 'user_min_distance'}, inplace=True)

    # 客户使用优惠券线下购买距离商店的最大距离
    t4 = t2.groupby('user_id').agg('max').reset_index()
    t4.rename(columns={'distance': 'user_max_distance'}, inplace=True)

    # 客户使用优惠券线下购买距离商店的平均距离
    t5 = t2.groupby('user_id').agg('mean').reset_index()
    t5.rename(columns={'distance': 'user_mean_distance'}, inplace=True)

    #客户使用优惠券线下购买距离商店的中间距离
    t6 = t2.groupby('user_id').agg('median').reset_index()
    t6.rename(columns={'distance': 'user_median_distance'}, inplace=True)

    # 客户使用优惠券购买的次数
    t7 = user[(user.date != 'null') & (user.coupon_id != 'null')][['user_id']]
    t7['buy_use_coupon'] = 1
    t7 = t7.groupby('user_id').agg('sum').reset_index()

    # 客户购买商品的总次数
    t8 = user[user.date != 'null'][['user_id']]
    t8['buy_total'] = 1
    t8 = t8.groupby('user_id').agg('sum').reset_index()

    # 客户收到优惠券的总数
    t9 = user[user.coupon_id != 'null'][['user_id']]
    t9['coupon_received'] = 1
    t9 = t9.groupby('user_id').agg('sum').reset_index()

    # 客户从收优惠券到消费的时间间隔
    t10 = user[(user.date_received != 'null') & (user.date != 'null')][['user_id', 'date_received', 'date']]
    t10['user_date_datereceived_gap'] = t10.date + ':' + t10.date_received
    # 下面调用user_date_datereceived_gap函数计算时间间隔
    t10.user_date_datereceived_gap = t10.user_date_datereceived_gap.apply(get_user_date_datereceived_gap)
    t10 = t10[['user_id', 'user_date_datereceived_gap']]

    # 客户从收优惠券到消费的平均时间间隔
    t11 = t10.groupby('user_id').agg('mean').reset_index()
    t11.rename(columns={'user_date_datereceived_gap': 'avg_user_date_datereceived_gap'}, inplace=True)

    # 客户从收优惠券到消费的最小时间间隔
    t12 = t10.groupby('user_id').agg('min').reset_index()
    t12.rename(columns={'user_date_datereceived_gap': 'min_user_date_datereceived_gap'}, inplace=True)

    # 客户从收优惠券到消费的最大时间间隔
    t13 = t10.groupby('user_id').agg('max').reset_index()
    t13.rename(columns={'user_date_datereceived_gap': 'max_user_date_datereceived_gap'}, inplace=True)

    # 数据合并，on为依靠的列名，how为融合的方法，left为只保留左表的所有数据
    user_feature = pd.merge(t, t1, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t3, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t4, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t5, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t6, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t7, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t8, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t9, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t11, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t12, on='user_id', how='left')
    user_feature = pd.merge(user_feature, t13, on='user_id', how='left')
    # 将空数据用0替代
    user_feature.count_merchant = user_feature.count_merchant.replace(np.nan, 0)
    user_feature.buy_use_coupon = user_feature.buy_use_coupon.replace(np.nan, 0)
    user_feature.buy_total = user_feature.buy_total.replace(np.nan, 0)
    user_feature.coupon_received = user_feature.coupon_received.replace(np.nan, 0)
    user_feature['buy_use_coupon_rate'] = user_feature.buy_use_coupon.astype(
        'float') / user_feature.buy_total.astype('float')
    user_feature['user_coupon_transfer_rate'] = user_feature.buy_use_coupon.astype(
        'float') / user_feature.coupon_received.astype('float')
    return user_feature


def GetMerchantRelatedFeature(feature): # 商品的特征
    merchant = feature[['merchant_id', 'coupon_id', 'distance', 'date_received', 'date']].copy()
    t = merchant[['merchant_id']].copy()
    # 删除重复行数据
    t.drop_duplicates(inplace=True)

    # 卖出的商品的商店
    t1 = merchant[merchant.date != 'null'][['merchant_id']].copy()
    t1['total_sales'] = 1

    # 每个商品的销售数量
    t1 = t1.groupby('merchant_id').agg('sum').reset_index()

    # 使用了优惠券消费的商品，正样本
    t2 = merchant[(merchant.date != 'null') & (merchant.coupon_id != 'null')][['merchant_id']].copy()
    t2['sales_use_coupon'] = 1
    t2 = t2.groupby('merchant_id').agg('sum').reset_index()

    # 商品的优惠券的总数量
    t3 = merchant[merchant.coupon_id != 'null'][['merchant_id']].copy()
    t3['total_coupon'] = 1
    t3 = t3.groupby('merchant_id').agg('sum').reset_index()

    # 使用了优惠券的商品的销量和距离的关系
    t4 = merchant[(merchant.date != 'null') & (merchant.coupon_id != 'null')][['merchant_id', 'distance']].copy()
    # 下面三行代码的主要作用就是为了将distance字段的数据类型转化为int
    # 把数据中的null值全部替换为-1
    t4.replace('null', -1, inplace=True)
    t4.distance = t4.distance.astype('int')
    # 再把数据中的-1全部替换为NaN
    t4.replace(-1, np.nan, inplace=True)

    # 返回用户离商品的距离最小值
    t5 = t4.groupby('merchant_id').agg('min').reset_index()
    t5.rename(columns={'distance': 'merchant_min_distance'}, inplace=True)

    # 返回用户离商品的距离最大值
    t6 = t4.groupby('merchant_id').agg('max').reset_index()
    t6.rename(columns={'distance': 'merchant_max_distance'}, inplace=True)

    # 返回距离的平均值
    t7 = t4.groupby('merchant_id').agg('mean').reset_index()
    t7.rename(columns={'distance': 'merchant_mean_distance'}, inplace=True)

    # 返回距离的中位值
    t8 = t4.groupby('merchant_id').agg('median').reset_index()
    t8.rename(columns={'distance': 'merchant_median_distance'}, inplace=True)

    merchant_feature = pd.merge(t, t1, on='merchant_id', how='left')
    merchant_feature = pd.merge(merchant_feature, t2, on='merchant_id', how='left')
    merchant_feature = pd.merge(merchant_feature, t3, on='merchant_id', how='left')
    merchant_feature = pd.merge(merchant_feature, t5, on='merchant_id', how='left')
    merchant_feature = pd.merge(merchant_feature, t6, on='merchant_id', how='left')
    merchant_feature = pd.merge(merchant_feature, t7, on='merchant_id', how='left')
    merchant_feature = pd.merge(merchant_feature, t8, on='merchant_id', how='left')

    # 将数据中的NaN用0来替换
    merchant_feature.sales_use_coupon = merchant_feature.sales_use_coupon.replace(np.nan, 0)
    # 将数据中的NaN用0来替换
    merchant_feature.total_coupon = merchant_feature.total_coupon.replace(np.nan, 0)

    # 优惠券的使用率
    merchant_feature['merchant_coupon_transfer_rate'] = merchant_feature.sales_use_coupon.astype(
        'float') / merchant_feature.total_coupon
    # 即卖出商品中使用优惠券的占比
    merchant_feature['coupon_rate'] = merchant_feature.sales_use_coupon.astype('float') / merchant_feature.total_sales

    return merchant_feature


def GetUserAndMerchantRelatedFeature(feature):
    all_user_merchant = feature[['user_id', 'merchant_id']].copy()
    all_user_merchant.drop_duplicates(inplace=True) # 去重

    # 一个客户在一个商家一共买的次数
    t = feature[['user_id', 'merchant_id', 'date']].copy()
    t = t[t.date != 'null'][['user_id', 'merchant_id']]
    t['user_merchant_buy_total'] = 1
    t = t.groupby(['user_id', 'merchant_id']).agg('sum').reset_index()
    t.drop_duplicates(inplace=True)

    # 一个客户在一个商家一共收到的优惠券
    t1 = feature[['user_id', 'merchant_id', 'coupon_id']]
    t1 = t1[t1.coupon_id != 'null'][['user_id', 'merchant_id']]
    t1['user_merchant_received'] = 1
    t1 = t1.groupby(['user_id', 'merchant_id']).agg('sum').reset_index()
    t1.drop_duplicates(inplace=True)

    # 一个客户在一个商家使用优惠券购买的次数
    t2 = feature[['user_id', 'merchant_id', 'date', 'date_received']]
    t2 = t2[(t2.date != 'null') & (t2.date_received != 'null')][['user_id', 'merchant_id']]
    t2['user_merchant_buy_use_coupon'] = 1
    t2 = t2.groupby(['user_id', 'merchant_id']).agg('sum').reset_index()
    t2.drop_duplicates(inplace=True)

    # 一个客户在一个商家浏览的次数
    t3 = feature[['user_id', 'merchant_id']]
    t3['user_merchant_any'] = 1
    t3 = t3.groupby(['user_id', 'merchant_id']).agg('sum').reset_index()
    t3.drop_duplicates(inplace=True)

    # 一个客户在一个商家没有使用优惠券购买的次数
    t4 = feature[['user_id', 'merchant_id', 'date', 'coupon_id']]
    t4 = t4[(t4.date != 'null') & (t4.coupon_id == 'null')][['user_id', 'merchant_id']]
    t4['user_merchant_buy_common'] = 1
    t4 = t4.groupby(['user_id', 'merchant_id']).agg('sum').reset_index()
    t4.drop_duplicates(inplace=True)

    # 数据合并
    user_merchant = pd.merge(all_user_merchant, t, on=['user_id', 'merchant_id'], how='left')
    user_merchant = pd.merge(user_merchant, t1, on=['user_id', 'merchant_id'], how='left')
    user_merchant = pd.merge(user_merchant, t2, on=['user_id', 'merchant_id'], how='left')
    user_merchant = pd.merge(user_merchant, t3, on=['user_id', 'merchant_id'], how='left')
    user_merchant = pd.merge(user_merchant, t4, on=['user_id', 'merchant_id'], how='left')

    # 去null和nan
    user_merchant.user_merchant_buy_use_coupon = user_merchant.user_merchant_buy_use_coupon.replace(np.nan, 0)
    user_merchant.user_merchant_buy_common = user_merchant.user_merchant_buy_common.replace(np.nan, 0)

    # 优惠卷的使用率
    user_merchant['user_merchant_coupon_transfer_rate'] = user_merchant.user_merchant_buy_use_coupon.astype(
        'float') / user_merchant.user_merchant_received.astype('float')

    user_merchant['user_merchant_coupon_buy_rate'] = user_merchant.user_merchant_buy_use_coupon.astype(
        'float') / user_merchant.user_merchant_buy_total.astype('float')
    user_merchant['user_merchant_rate'] = user_merchant.user_merchant_buy_total.astype(
        'float') / user_merchant.user_merchant_any.astype('float')
    user_merchant['user_merchant_common_buy_rate'] = user_merchant.user_merchant_buy_common.astype(
        'float') / user_merchant.user_merchant_buy_total.astype('float')

    return user_merchant


def get_discount_man(s):
    s = str(s)
    s = s.split(':')
    if len(s)==1:
        return 'null'
    else:
        return int(s[0])


def get_discount_jian(s):
    s = str(s)
    s = s.split(':')
    if len(s) == 1:
        return 'null'
    else:
        return int(s[1])


def is_man_jian(s):
    s = str(s)
    s = s.split(':')
    if len(s) == 1:
        return 0
    else:
        return 1


def calc_discount_rate(s):
    s = str(s)
    s = s.split(':')
    if len(s) == 1:
        return float(s[0])
    else:
        return 1.0 - float(s[1]) / float(s[0])


def GetCouponRelatedFeature(dataset, feature):
    # 这里的feature只是用来作为划分日期的分界线
    # 为了求得每个feature中date最大的日期，其会被用在求days_distance字段
    t = feature[feature['date'] != 'null']['date'].unique()
    t = max(t)  # 最大的data

    # 获得日期是星期几,注意返回的是0-6，即一星期的第几天
    dataset['day_of_week'] = dataset.date_received.astype('str').apply(
        lambda x: date(int(x[0:4]), int(x[4:6]), int(x[6:8])).weekday() + 1)    # lambda简化了函数定义的书写形式
    # 领取的优惠卷是一个月的第几天
    dataset['day_of_month'] = dataset.date_received.astype('str').apply(lambda x: int(x[6:8]))


# 显示时期和截止日之间的天数，截至日期就是feature中的最后一天用卷的日期，是t
    dataset['days_distance'] = dataset.date_received.astype('str').apply(
        lambda x: (date(int(x[0:4]), int(x[4:6]), int(x[6:8])) - date(int(t[0:4]), int(t[4:6]), int(t[6:8]))).days)
    # 显示满了多少钱后开始减
    dataset['discount_man'] = dataset.discount_rate.apply(get_discount_man)
    # 显示满减的减少的钱
    dataset['discount_jian'] = dataset.discount_rate.apply(get_discount_jian)
    # 返回优惠券是否是满减券
    dataset['is_man_jian'] = dataset.discount_rate.apply(is_man_jian)
    # 显示打折力度
    dataset['discount_rate'] = dataset.discount_rate.apply(calc_discount_rate)

    # 显示每一种优惠券的数量
    d = dataset[['coupon_id']]
    d['coupon_count'] = 1
    d = d.groupby('coupon_id').agg('sum').reset_index()

    # 数据合并
    dataset = pd.merge(dataset, d, on='coupon_id', how='left')

    return dataset


def is_firstlastone(x):
    if x==0:
        return 1
    elif x>0:
        return 0
    else:
        return -1


def get_day_gap_before(s):
        date_received, dates = s.split('-')
        dates = dates.split(':')
        gaps = []
        for d in dates:
            # 将时间差转化为天数
            this_gap = (dt.date(int(date_received[0:4]), int(date_received[4:6]), int(date_received[6:8])) - dt.date(
                int(d[0:4]), int(d[4:6]), int(d[6:8]))).days
            if this_gap > 0:
                gaps.append(this_gap)
        if len(gaps) == 0:
            return -1
        else:
            return min(gaps)


def get_day_gap_after(s):
        date_received, dates = s.split('-')
        dates = dates.split(':')
        gaps = []
        for d in dates:
            this_gap = (dt.datetime(int(d[0:4]), int(d[4:6]), int(d[6:8])) - dt.datetime(int(date_received[0:4]),
                                                                                         int(date_received[4:6]),
                                                                                         int(date_received[6:8]))).days
            if this_gap > 0:
                gaps.append(this_gap)
        if len(gaps) == 0:
            return -1
        else:
            return min(gaps)


def GetOtherFeature(dataset):
    # 收到的总优惠券数
    t = dataset[['user_id']].copy()
    t['this_month_user_receive_all_coupon_count'] = 1
    t = t.groupby('user_id').agg('sum').reset_index()

    # 收到的相同的优惠券的数目
    t1 = dataset[['user_id', 'coupon_id']].copy()
    t1['this_month_user_receive_same_coupn_count'] = 1
    t1 = t1.groupby(['user_id', 'coupon_id']).agg('sum').reset_index()

    t2 = dataset[['user_id', 'coupon_id', 'date_received']].copy()
    t2.date_received = t2.date_received.astype('str')

    # 如果出现相同的用户接收相同的优惠券在接收时间上用‘：’连接上第n次接受优惠券的时间
    t2 = t2.groupby(['user_id', 'coupon_id'])['date_received'].agg(lambda x: ':'.join(x)).reset_index()

    # 将接收时间的一组按着':'分开，这样就可以计算接受了优惠券的数量,apply是合并
    t2['receive_number'] = t2.date_received.apply(lambda s: len(s.split(':')))
    t2 = t2[t2.receive_number > 1]

    # 最大接受的日期
    t2['max_date_received'] = t2.date_received.apply(lambda s: max([int(d) for d in s.split(':')]))

    # 最小的接收日期
    t2['min_date_received'] = t2.date_received.apply(lambda s: min([int(d) for d in s.split(':')]))
    t2 = t2[['user_id', 'coupon_id', 'max_date_received', 'min_date_received']]

    t3 = dataset[['user_id', 'coupon_id', 'date_received']]
    # 将两表融合只保留左表数据,这样得到的表，相当于保留了最近接收时间和最远接受时间
    t3 = pd.merge(t3, t2, on=['user_id', 'coupon_id'], how='left')
    # 这个优惠券最近接受时间
    t3['this_month_user_receive_same_coupon_lastone'] = t3.max_date_received - t3.date_received.astype(int)
    # 这个优惠券最远接受时间
    t3['this_month_user_receive_same_coupon_firstone'] = t3.date_received.astype(int) - t3.min_date_received

    t3.this_month_user_receive_same_coupon_lastone = t3.this_month_user_receive_same_coupon_lastone.apply(
        is_firstlastone)
    t3.this_month_user_receive_same_coupon_firstone = t3.this_month_user_receive_same_coupon_lastone.apply(
        is_firstlastone)
    t3 = t3[['user_id', 'coupon_id', 'date_received', 'this_month_user_receive_same_coupon_lastone',
             'this_month_user_receive_same_coupon_firstone']]

    # 提取第四个特征,一个用户所接收到的所有优惠券的数量
    t4 = dataset[['user_id', 'date_received']].copy()
    t4['this_day_receive_all_coupon_count'] = 1
    t4 = t4.groupby(['user_id', 'date_received']).agg('sum').reset_index()

    # 提取第五个特征,一个用户不同时间所接收到不同优惠券的数量
    t5 = dataset[['user_id', 'coupon_id', 'date_received']].copy()
    t5['this_day_user_receive_same_coupon_count'] = 1
    t5 = t5.groupby(['user_id', 'coupon_id', 'date_received']).agg('sum').reset_index()

    # 一个用户不同优惠券的接受时间
    t6 = dataset[['user_id', 'coupon_id', 'date_received']].copy()
    t6.date_received = t6.date_received.astype('str')
    t6 = t6.groupby(['user_id', 'coupon_id'])['date_received'].agg(lambda x: ':'.join(x)).reset_index()
    t6.rename(columns={'date_received': 'dates'}, inplace=True)

    t7 = dataset[['user_id', 'coupon_id', 'date_received']]
    t7 = pd.merge(t7, t6, on=['user_id', 'coupon_id'], how='left')
    t7['date_received_date'] = t7.date_received.astype('str') + '-' + t7.dates      # 这个dates来自t6
    t7['day_gap_before'] = t7.date_received_date.apply(get_day_gap_before)
    t7['day_gap_after'] = t7.date_received_date.apply(get_day_gap_after)
    t7 = t7[['user_id', 'coupon_id', 'date_received', 'day_gap_before', 'day_gap_after']]

    other_feature = pd.merge(t1, t, on='user_id')
    other_feature = pd.merge(other_feature, t3, on=['user_id', 'coupon_id'])
    other_feature = pd.merge(other_feature, t4, on=['user_id', 'date_received'])
    other_feature = pd.merge(other_feature, t5, on=['user_id', 'coupon_id', 'date_received'])
    other_feature = pd.merge(other_feature, t7, on=['user_id', 'coupon_id', 'date_received'])

    return other_feature


# 给数据打标签
def get_label(s):
    s = s.split(':')
    if s[0] == 'null':
        return 0
    elif (date(int(s[0][0:4]), int(s[0][4:6]), int(s[0][6:8]))-
          date(int(s[1][0:4]), int(s[1][4:6]), int(s[1][6:8]))).days <= 15:
        return 1    # 正数据
    else:
        return -1


def DataProcess(dataset, feature, TrainFlag):   # 特征工程的主函数
    user = GetUserRelatedFeature(feature)
    merchant = GetMerchantRelatedFeature(feature)
    user_merchant = GetUserAndMerchantRelatedFeature(feature)
    coupon = GetCouponRelatedFeature(dataset, feature)
    other_feature = GetOtherFeature(dataset)

    # 特征合并
    dataset = pd.merge(coupon, merchant, on='merchant_id', how='left')
    dataset = pd.merge(dataset, user, on='user_id', how='left')
    dataset = pd.merge(dataset, user_merchant, on=['user_id', 'merchant_id'], how='left')
    dataset = pd.merge(dataset, other_feature, on=['user_id', 'coupon_id', 'date_received'], how='left')
    dataset.drop_duplicates(inplace=True)

    # 替换nan值
    dataset.user_merchant_buy_total = dataset.user_merchant_buy_total.replace(np.nan, 0)
    dataset.user_merchant_any = dataset.user_merchant_any.replace(np.nan, 0)
    dataset.user_merchant_received = dataset.user_merchant_received.replace(np.nan, 0)

    # 是周末则赋值为1
    dataset['is_weekend'] = dataset.day_of_week.apply(lambda x: 1 if x in (6, 7) else 0)

    # 使用get_dummies独立热编码，离散数据常用方法
    weekday_dummies = pd.get_dummies(dataset.day_of_week)
    weekday_dummies.columns = ['weekday' + str(i + 1) for i in range(weekday_dummies.shape[1])]
    # 使用concat进行数据合并和重塑, axis = 1表示合并是跨列进行的
    dataset = pd.concat([dataset, weekday_dummies], axis=1)

    if TrainFlag:       # 如果是训练集
        dataset['date'] = dataset['date'].fillna('null');
        dataset['label'] = dataset.date.astype('str') + ':' + dataset.date_received.astype('str')
        dataset.label = dataset.label.apply(get_label)
        # 最终提交结果用不上的列丢弃
        dataset.drop(['merchant_id', 'day_of_week', 'date', 'date_received', 'coupon_count'], axis=1, inplace=True)
    else:       # 不然就是测试集
        dataset.drop(['merchant_id', 'day_of_week', 'coupon_count'], axis=1, inplace=True)

    dataset = dataset.replace('null', np.nan)
    return dataset


# 开始提取特征
ProcessDataSet1 = DataProcess(dataset1, feature1, True)
ProcessDataSet1.to_csv(os.path.join(ProcessedPath, 'ProcessDataSet1.csv'),index=None)
print('---------------ProcessDataSet1 done-------------------')
ProcessDataSet2 = DataProcess(dataset2, feature2, True)
ProcessDataSet2.to_csv(os.path.join(ProcessedPath, 'ProcessDataSet2.csv'),index=None)
print('---------------ProcessDataSet2 done-------------------')
# 测试集
ProcessDataSet3 = DataProcess(dataset3, feature3, False)
ProcessDataSet3.to_csv(os.path.join(ProcessedPath, 'ProcessDataSet3.csv'),index=None)
print('---------------ProcessDataSet3 done-------------------')

# 查看内容
# print(ProcessDataSet1.head(5))
# print(ProcessDataSet3.head(5))




# 以下是模型训练及输出结果过程
Process1 = pd.read_csv('D:/tianchi/O2O/O2O_data/ProcessDataSet1.csv')
Process2 = pd.read_csv('D:/tianchi/O2O/O2O_data/ProcessDataSet2.csv')
Process3 = pd.read_csv('D:/tianchi/O2O/O2O_data/ProcessDataSet3.csv')


Process1.label.replace(-1, 0, inplace=True)
Process2.label.replace(-1, 0, inplace=True)
# ProcessDataSet3没得标签
Process1.drop_duplicates(inplace=True)
Process2.drop_duplicates(inplace=True)
Process3.drop_duplicates(inplace=True)

# 合并
Process12 = pd.concat([Process1, Process2], axis=0)    # axis=0是跨行
Process12_y = Process12.label
Process12_x = Process12.drop(['user_id', 'label', 'day_gap_before', 'day_gap_after'], axis=1)

Process3_preds = Process3[['user_id', 'coupon_id', 'date_received']]
Process3_x = Process3.drop(['user_id', 'coupon_id', 'date_received', 'day_gap_before',
                                          'day_gap_after'], axis=1)

# Xgboost训练的数据必须要使用xgb.DMatrix()转化后的形式
# dataTrain = xgb.DMatrix(ProcessDataSet12_x, label=ProcessDataSet12_y)
dataTrain = xgb.DMatrix(Process12_x, label=Process12_y)
# 注意x,y的大小写！！！
dataTest = xgb.DMatrix(Process3_x)


# 自己定义的性能评价函数
def myauc(test):
    testgroup = test.groupby(['coupon_id'])
    aucs = []
    for i in testgroup:
        tmpdf = i[1]
        if len(tmpdf['label'].unique()) != 2:
            continue
        fpr, tpr, thresholds = roc_curve(tmpdf['label'], tmpdf['pred'], pos_label=1)
        aucs.append(auc(fpr, tpr))
    return np.average(aucs)

# 这里超参数的值来自wepe大佬，是经过多次优化的结果
params = {'booster': 'gbtree',
          'objective': 'binary:logistic',
          'eval_metric': 'auc',
          'gamma': 0.1,
          'min_child_weight': 1.1,
          'max_depth': 5,
          'lambda': 10,
          'subsample': 0.7,
          'colsample_bytree': 0.7,
          'colsample_bylever': 0.7,
          'eta': 0.01,
          'tree_method': 'exact',
          'seed': 0,
          'nthread': 3
          }
watchlist = [(dataTrain, 'train')]
model = xgb.train(params, dataTrain, num_boost_round=3500, evals=watchlist)

model.save_model('D:/tianchi/O2O/O2O_data/xgbmodel')
model = xgb.Booster(params)
model.load_model('D:/tianchi/O2O/O2O_data/xgbmodel')

# 正式开始预测结果
Process3_preds1 = Process3_preds
Process3_preds1['label'] = model.predict(dataTest)
# 标签归一化在[0, 1]
# Process3_preds1.label = MinMaxScaler(copy=True, feature_range=(0, 1).fit_transform(Process3_preds1.label.reshape(-1, 1)))
Process3_preds1.label = MinMaxScaler(copy=True, feature_range=(0, 1)).fit_transform(Process3_preds1.label.values.reshape(-1,1))
# 排序
Process3_preds1.sort_values(by=['coupon_id', 'label'], inplace=True)
Process3_preds1.to_csv('D:/tianchi/O2O/O2O_data/xgb_preds.csv', index=None, header=None)
print(Process3_preds1.describe())



