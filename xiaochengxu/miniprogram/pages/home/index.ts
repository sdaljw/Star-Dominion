Page({
  data: {
    query: '',
    categories: [
      { id: 'dev', name: '开发工具', count: 29 },
      { id: 'calc', name: '计算器', count: 16 },
      { id: 'text', name: '文本工具', count: 9 },
      { id: 'fun', name: '趣味工具', count: 7 },
    ],
    featuredTools: [
      { id: 'json-format', name: 'JSON 格式化', description: '格式化、压缩和校验 JSON' },
      { id: 'bmi-calculator', name: 'BMI 计算器', description: '输入身高体重快速计算 BMI' },
      { id: 'password-gen', name: '密码生成器', description: '生成安全随机密码' },
      { id: 'word-count', name: '字数统计', description: '统计字符、词语和行数' },
    ],
  },

  onSearchInput(event: WechatMiniprogram.Input) {
    this.setData({ query: event.detail.value });
  },

  openCategory(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.IAnyObject>) {
    const category = String(event.currentTarget.dataset.category ?? '');
    wx.navigateTo({ url: `/pages/category/index?category=${encodeURIComponent(category)}` });
  },

  openTool(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.IAnyObject>) {
    const id = String(event.currentTarget.dataset.id ?? '');
    wx.navigateTo({ url: `/pages/tool/index?id=${encodeURIComponent(id)}` });
  },

  onShareAppMessage() {
    return {
      title: '逐梦工具箱｜常用在线工具',
      path: '/pages/home/index',
    };
  },
});
