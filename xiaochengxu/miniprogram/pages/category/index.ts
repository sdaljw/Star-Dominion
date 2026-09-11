Page({
  data: {
    category: '',
    title: '工具分类',
    tools: [] as Array<{ id: string; name: string; description: string }>,
  },

  onLoad(options: Record<string, string | undefined>) {
    const category = options.category ?? '';
    this.setData({
      category,
      title: category ? `${category}工具` : '全部工具',
      tools: [],
    });
  },

  openTool(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.IAnyObject>) {
    const id = String(event.currentTarget.dataset.id ?? '');
    wx.navigateTo({ url: `/pages/tool/index?id=${encodeURIComponent(id)}` });
  },
});
