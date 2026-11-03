/**
 * contracts.js - Verwaltung und Darstellung von Verträgen & DSGVO
 * Lädt Verträge dynamisch aus dem /Companion/res/ Ordner.
 */

class ContractManager {
  constructor() {
    this.contractsIndex = [];
    this.loadedContracts = new Map();
    this.consentStates = new Map(); // contractId -> { checkboxId: boolean }
    this.activeContractTab = null;
  }

  async init() {
    try {
      const res = await fetch('res/contracts_index.json?v=' + Date.now());
      if (res.ok) {
        const data = await res.json();
        this.contractsIndex = data.contracts || [];
      } else {
        console.warn('contracts_index.json konnte nicht geladen werden, verwende Fallback');
        this.contractsIndex = this.getFallbackIndex();
      }
    } catch (e) {
      console.warn('Ladefehler contracts_index:', e);
      this.contractsIndex = this.getFallbackIndex();
    }

    // Lade alle aktivierten Verträge
    for (const item of this.contractsIndex) {
      if (item.enabled) {
        await this.loadContract(item);
      }
    }
  }

  getFallbackIndex() {
    return [
      {
        id: "dsgvo_datenverarbeitung",
        file: "dsgvo_datenverarbeitung.json",
        title: "Einwilligung zur Datenverarbeitung (DSGVO)",
        badge: "Pflicht",
        required: true,
        enabled: true,
        version: "2026.1"
      },
      {
        id: "behandlungsvertrag",
        file: "behandlungsvertrag.json",
        title: "Behandlungs- & Honorarvereinbarung",
        badge: "Empfohlen",
        required: false,
        enabled: false,
        version: "2026.1"
      }
    ];
  }

  async loadContract(item) {
    try {
      const res = await fetch(`res/${item.file}?v=` + Date.now());
      if (res.ok) {
        const contractData = await res.json();
        this.loadedContracts.set(item.id, contractData);
      } else {
        console.error(`Fehler beim Laden von res/${item.file}`);
      }
    } catch (e) {
      console.error(`Netzwerkfehler bei res/${item.file}:`, e);
    }
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
    for (const c of activeContracts) {
      const contract = this.loadedContracts.get(c.id);
      if (!contract) continue;

      if (contract.checkboxes) {
        for (const cb of contract.checkboxes) {
          if (cb.required && !this.getCheckboxState(c.id, cb.id)) {
            return false;
          }
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
    const activeContracts = this.getActiveContracts();

    for (const c of activeContracts) {
      const contract = this.loadedContracts.get(c.id);
      if (!contract) continue;

      const checkboxesState = {};
      if (contract.checkboxes) {
        for (const cb of contract.checkboxes) {
          checkboxesState[cb.id] = {
            label: cb.label,
            checked: this.getCheckboxState(c.id, cb.id),
            required: !!cb.required
          };
        }
      }

      signedContracts.push({
        id: contract.id,
        title: contract.title,
        version: contract.version || '1.0',
        required: !!c.required,
        timestamp: timestamp,
        readableDate: readableDate,
        checkboxes: checkboxesState
      });
    }

    return {
      timestamp: timestamp,
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
