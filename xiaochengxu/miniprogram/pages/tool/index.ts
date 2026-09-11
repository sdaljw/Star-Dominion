Page({
  data: {
    id: '',
    title: '工具详情',
    description: '',
    status: 'adapting',
  },

  onLoad(options: Record<string, string | undefined>) {
    this.setData({ id: options.id ?? '' });
  },

  goBack() {
    wx.navigateBack({ delta: 1 });
  },
});
