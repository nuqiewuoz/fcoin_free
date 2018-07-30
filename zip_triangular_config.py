sleepsecond = 0.5  # 每单结束后的休息时间
s1 = 'zip'
s2 = 'eth'
s3 = 'usdt'
# 为了减少计算量，避免单位换算
_s2amount = 0.01
_s1amount = 1000  # 0.01*100000
# 超过halfs1和halfs2，就可以下单，默认为一半
halfs1 = _s1amount/2
halfs2 = _s2amount/2

# 套利比例，1.001意味着1‰
difference = 1.001
is_use_amount = False
