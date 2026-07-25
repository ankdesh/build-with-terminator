import createKLayoutModule from './klayout_db.js';

let moduleInstance = null;

export async function getKLayout() {
  if (!moduleInstance) {
    moduleInstance = await createKLayoutModule();
  }
  return moduleInstance;
}

export default createKLayoutModule;
