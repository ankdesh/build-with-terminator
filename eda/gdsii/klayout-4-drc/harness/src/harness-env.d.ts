import type { Context } from "@deepseek-ai/cordis";

declare module "@deepseek-ai/cordis" {
  interface Context {
    flows: {
      registerOperation(operation: any): () => void;
      registerDefinition(definition: any): () => void;
      catalog(context: string): readonly any[];
      compile(ref: any): any;
      start(request: any): Promise<any>;
      settled(id: string): Promise<any>;
      get(id: string, actor: any): any;
      list(actor: any): readonly any[];
    };
  }
}
