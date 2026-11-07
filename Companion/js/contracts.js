/**
 * Verwaltung und lokale Speicherung der vom Praxis-PC importierten Verträge.
 */
class ContractManager {
  constructor() {
    this.contractsIndex = [];
    this.loadedContracts = new Map();
    this.consentStates = new Map();
    this.activeContractTab = null;
  }

  async init() {
    const savedContracts = localStorage.getItem('leprendix_companion_contracts');
    if (!savedContracts) return;

    try {
      const contracts = JSON.parse(savedContracts);
      this.replaceContracts(contracts, false);
    } catch (error) {
      console.error('Lokal gespeicherte Verträge konnten nicht geladen werden:', error);
    }
  }

  validateContract(contract) {
    if (!contract || typeof contract !== 'object' || Array.isArray(contract)) {
      throw new Error('Die Vertragsdatei muss ein JSON-Objekt enthalten.');
    }
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(contract.id || '') || contract.id === 'contracts_index') {
      throw new Error('Die Vertrags-ID ist ungültig.');
    }
    if (typeof contract.title !== 'string' || !contract.title.trim()) {
      throw new Error('Der Vertragstitel fehlt.');
    }
    if (contract.required !== undefined && typeof contract.required !== 'boolean') {
      throw new Error(`Der Vertrag „${contract.title}“ hat eine ungültige Pflicht-Angabe.`);
    }
    if (!Array.isArray(contract.sections) || !contract.sections.length) {
      throw new Error(`Der Vertrag „${contract.title}“ enthält keine Abschnitte.`);
    }
    if (contract.sections.some(section =>
      !section || typeof section.heading !== 'string' || typeof section.text !== 'string'
    )) {
      throw new Error(`Der Vertrag „${contract.title}“ enthält einen ungültigen Abschnitt.`);
    }
    if (!Array.isArray(contract.checkboxes || [])) {
      throw new Error(`Der Vertrag „${contract.title}“ enthält ungültige Zustimmungspunkte.`);
    }
    const checkboxIds = new Set();
    for (const checkbox of contract.checkboxes || []) {
      if (
        !checkbox ||
        typeof checkbox.id !== 'string' ||
        !checkbox.id.trim() ||
        typeof checkbox.label !== 'string' ||
        (checkbox.required !== undefined && typeof checkbox.required !== 'boolean') ||
        checkboxIds.has(checkbox.id)
      ) {
        throw new Error(`Der Vertrag „${contract.title}“ enthält einen ungültigen Zustimmungspunkt.`);
      }
      checkboxIds.add(checkbox.id);
    }
    return contract;
  }

  replaceContracts(contracts, persist = true) {
    if (!Array.isArray(contracts)) {
      throw new Error('Die Vertragsliste ist ungültig.');
    }

    const nextContracts = new Map();
    for (const rawContract of contracts) {
      const contract = {
        ...this.validateContract(rawContract),
        enabled: rawContract.enabled !== false
      };
      if (nextContracts.has(contract.id)) {
        throw new Error(`Die Vertrags-ID „${contract.id}“ ist mehrfach vorhanden.`);
      }
      nextContracts.set(contract.id, contract);
    }

    if (persist) {
      localStorage.setItem(
        'leprendix_companion_contracts',
        JSON.stringify(Array.from(nextContracts.values()))
      );
    }

    this.loadedContracts = nextContracts;
    this.contractsIndex = Array.from(nextContracts.values()).map(contract => ({
      id: contract.id,
      file: `${contract.id}.json`,
      title: contract.title,
      badge: contract.required ? 'Pflicht' : 'Optional',
      required: !!contract.required,
      enabled: contract.enabled,
      version: contract.version || '1.0'
    }));
    this.consentStates.clear();
  }

  async importFiles(files) {
    const imported = [];
    const seenIds = new Set();
    for (const file of files) {
      if (file.size > 2 * 1024 * 1024) {
        throw new Error(`${file.name}: Die Datei ist größer als 2 MB.`);
      }
      let contract;
      try {
        contract = JSON.parse(await file.text());
      } catch (error) {
        throw new Error(`${file.name}: Die JSON-Datei ist ungültig.`);
      }
      const validated = this.validateContract(contract);
      if (seenIds.has(validated.id)) {
        throw new Error(`${file.name}: Diese Vertrags-ID wurde mehrfach ausgewählt.`);
      }
      seenIds.add(validated.id);
      imported.push(validated);
    }

    const merged = new Map(this.loadedContracts);
    for (const contract of imported) {
      const previous = merged.get(contract.id);
      merged.set(contract.id, {
        ...contract,
        enabled: previous ? previous.enabled !== false : true
      });
    }
    this.replaceContracts(Array.from(merged.values()));
    return imported.length;
  }

  setContractEnabled(contractId, enabled) {
    const contract = this.loadedContracts.get(contractId);
    if (!contract || contract.required) return;
    const newEnabled = !!enabled;
    const nextContracts = Array.from(this.loadedContracts.values()).map(item =>
      item.id === contractId ? { ...item, enabled: newEnabled } : item
    );
    localStorage.setItem(
      'leprendix_companion_contracts',
      JSON.stringify(nextContracts)
    );

    contract.enabled = newEnabled;
    const indexItem = this.contractsIndex.find(item => item.id === contractId);
    if (indexItem) indexItem.enabled = contract.enabled;
  }

  getActiveContracts() {
    return this.contractsIndex.filter(c => c.enabled && this.loadedContracts.has(c.id));
  }

  getContract(id) {
    return this.loadedContracts.get(id);
  }

  setCheckboxState(contractId, checkboxId, isChecked) {
    if (!this.consentStates.has(contractId)) {
      this.consentStates.set(contractId, {});
    }
    this.consentStates.get(contractId)[checkboxId] = !!isChecked;
  }

  getCheckboxState(contractId, checkboxId) {
    if (!this.consentStates.has(contractId)) return false;
    return !!this.consentStates.get(contractId)[checkboxId];
  }

  areAllRequiredConsented() {
    const activeContracts = this.getActiveContracts();
    for (const item of activeContracts) {
      const contract = this.loadedContracts.get(item.id);
      if (!contract) continue;

      for (const checkbox of contract.checkboxes || []) {
        if (checkbox.required && !this.getCheckboxState(item.id, checkbox.id)) {
          return false;
        }
      }
    }
    return true;
  }

  generateSignedSummary(patientInfo, signatureDataUrl) {
    const now = new Date();
    const timestamp = now.toISOString();
    const readableDate = now.toLocaleDateString('de-AT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });

    const signedContracts = [];
    for (const item of this.getActiveContracts()) {
      const contract = this.loadedContracts.get(item.id);
      if (!contract) continue;

      const checkboxesState = {};
      for (const checkbox of contract.checkboxes || []) {
        checkboxesState[checkbox.id] = {
          label: checkbox.label,
          checked: this.getCheckboxState(item.id, checkbox.id),
          required: !!checkbox.required
        };
      }

      signedContracts.push({
        id: contract.id,
        title: contract.title,
        version: contract.version || '1.0',
        required: !!item.required,
        timestamp,
        readableDate,
        checkboxes: checkboxesState
      });
    }

    return {
      timestamp,
      signedDate: readableDate,
      patient: {
        titel: patientInfo.titel || '',
        anrede: patientInfo.anrede || '',
        vorname: patientInfo.vorname || '',
        nachname: patientInfo.nachname || '',
        vsnr: patientInfo.vsnr || '',
        krankenkasse: patientInfo.krankenkasse || '',
        adresse: `${patientInfo.strasse || ''} ${patientInfo.hausnummer || ''}${patientInfo.adresszusatz ? ', ' + patientInfo.adresszusatz : ''}, ${patientInfo.plz || ''} ${patientInfo.ort || ''}`.trim()
      },
      contracts: signedContracts,
      signatureImage: signatureDataUrl
    };
  }
}
