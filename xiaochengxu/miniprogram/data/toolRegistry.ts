import { NATIVE_CATEGORIES } from './categories';
import { NativeCategoryDefinition, NativeToolDefinition } from '../types/tool';

const route = '/pages/tool/index';

export const NATIVE_TOOLS: NativeToolDefinition[] = [
  {
    id: 'json-format',
    name: 'JSON 格式化',
    description: '格式化、压缩和校验 JSON',
    category: 'dev',
    icon: 'code',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['json', '格式化', '压缩', '校验'],
  },
  {
    id: 'json-minify',
    name: 'JSON 压缩',
    description: '压缩 JSON 去除空白',
    category: 'dev',
    icon: 'code',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['json', '压缩', 'minify'],
  },
  {
    id: 'json-validate',
    name: 'JSON 校验',
    description: '检查 JSON 语法并定位错误',
    category: 'dev',
    icon: 'check',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['json', '校验', 'validate'],
  },
  {
    id: 'bmi-calculator',
    name: 'BMI 计算器',
    description: '输入身高体重快速计算 BMI',
    category: 'calc',
    icon: 'calculator',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['bmi', '体重', '健康', '计算'],
  },
  {
    id: 'percentage-calculator',
    name: '百分比计算器',
    description: '完成百分比、增长率和占比计算',
    category: 'calc',
    icon: 'calculator',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['百分比', '增长率', '计算'],
  },
  {
    id: 'password-gen',
    name: '密码生成器',
    description: '生成安全随机密码',
    category: 'general',
    icon: 'key',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['密码', '随机', '安全'],
  },
  {
    id: 'random-number',
    name: '随机数生成器',
    description: '生成指定范围内的随机数字',
    category: 'fun',
    icon: 'dice',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['随机数', '抽签', 'random'],
  },
  {
    id: 'word-count',
    name: '字数统计',
    description: '统计字符、词语和行数',
    category: 'document',
    icon: 'text',
    capability: 'local',
    route,
    status: 'ready',
    tags: ['字数', '字符', '统计', '文本'],
  },
];

export { NATIVE_CATEGORIES };

export function getNativeToolById(id: string): NativeToolDefinition | undefined {
  return NATIVE_TOOLS.find((tool) => tool.id === id);
}

export function getNativeToolsByCategory(category: string): NativeToolDefinition[] {
  return NATIVE_TOOLS.filter((tool) => tool.category === category);
}

export function searchNativeTools(query: string): NativeToolDefinition[] {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return NATIVE_TOOLS.filter((tool) => tool.status === 'ready');

  return NATIVE_TOOLS.filter((tool) => {
    const haystack = [tool.name, tool.description, ...tool.tags].join(' ').toLocaleLowerCase();
    return haystack.includes(needle) && tool.status === 'ready';
  });
}

export function getNativeCategoryById(id: string): NativeCategoryDefinition | undefined {
  return NATIVE_CATEGORIES.find((category) => category.id === id);
}
