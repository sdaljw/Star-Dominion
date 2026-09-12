declare class URLSearchParams {
  constructor(init?: string);
  set(name: string, value: string): void;
  forEach(callback: (value: string, key: string) => void): void;
  toString(): string;
}

declare class URL {
  constructor(url: string, base?: string);
  readonly protocol: string;
  readonly hostname: string;
  readonly port: string;
  readonly host: string;
  readonly pathname: string;
  readonly hash: string;
  readonly origin: string;
  readonly username: string;
  readonly password: string;
  readonly search: string;
  readonly searchParams: URLSearchParams;
  toString(): string;
}
