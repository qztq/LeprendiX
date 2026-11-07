/**
 * app.js - Hauptlogik der LeprendiX Companion Web App
 * Beinhaltet:
 * 1. Start-Dashboard mit Daten-Statistiken, QR-Code Scanner & Neu-Erfassung
 * 2. Eigene, integrierte Bildschirmtastatur (keine störende Systemtastatur)
 * 3. Pre-Sync Überprüfung: Hausbesuch-Erkennung, Distanzberechnung & Kilometergeld
 * 4. Animierter Ladebalken während der Übertragung & automatische Patientenerstellung
 * 5. Titel fest mit der Anrede verknüpft (z. B. "Herr Dr.")
 * 6. Bereinigte Ansicht (ohne rechte Hilfe, ohne PLZ-Schnellwahl)
 */

class CompanionApp {
  constructor() {
    this.currentMode = 'dashboard'; // 'dashboard' | 'patient' | 'admin'
    this.currentStep = 1;
    this.totalSteps = 6;

    // Gesammelte Daten des aktuellen Patienten
    this.formData = {
      anrede: 'Frau',
      titel: [],
      customTitel: '',
      vorname: '',
      nachname: '',
      vsnrNummer: '',       // 4-stellig
      vsnrGeburtsdatum: '', // 6-stellig TTMMJJ
      vsnrFull: '',
      strasse: '',
      hausnummer: '',
      adresszusatz: '',
      plz: '',
      ort: '',
      krankenkasse: ''
    };

    // Verbindungsdaten zu LeprendiX mobile_connect.py
    this.connection = {
      host: window.location.hostname || '127.0.0.1',
      port: window.location.port ? parseInt(window.location.port, 10) : 5000,
      token: '',
      connected: false,
      lastCheck: null
    };

    // Admin & Praxis Konfiguration
    this.config = {
      adminPin: '1234',
      praxisName: 'Wundpraxis Moedling',
      praxisAdresse: 'Triesterstraße 10/4, 2351 Wiener Neudorf',
      autoResetSeconds: 12
    };

    // Lokaler Speicher für Offline-Patientendatensätze
    this.localRecords = [];
    this.activeLogFilter = 'all';

    // Module & Helfer
    this.contracts = new ContractManager();
    this.contractSyncRetryAt = 0;
    this.appVersion = '';
    this.signaturePad = null;
    this.activeNumpadTarget = 'vsnrNummer';

    // Integrierte Bildschirmtastatur (Punkt 1)
    this.activeKeyboardInput = null;
    this.keyboardMode = 'letters'; // 'letters' | 'symbols' | 'numeric'
    this.isShifted = true; // Anfangsbuchstabe standardmäßig groß

    // QR-Scanner Stream
    this.qrStream = null;
    this.qrScanInterval = null;

    this.init();
  }

  async init() {
    this.registerServiceWorker();
    this.loadPersistedState();
    this.parseUrlParams();
    await this.contracts.init();
    this.initSignaturePad();
    this.setupEventListeners();
    this.setupFirstRunWizard();
    this.setupCustomKeyboard();
    this.updateDashboardStats();
    await this.checkConnection();
    this.showFirstRunWizard();
    window.setTimeout(() => this.checkForUpdatesMonthly(), 2000);
    window.addEventListener('online', () => this.checkForUpdatesMonthly());

    // Startansicht: Standardmäßig das Dashboard anzeigen (Punkt 1)
    this.switchView('dashboard');

    // Regelmäßige Status-Prüfung alle 5 Sekunden
    setInterval(() => this.checkConnection(true), 5000);
  }

  showAppDialog(title, message, options = {}) {
    const dialog = document.getElementById('appDialog');
    const titleEl = document.getElementById('appDialogTitle');
    const messageEl = document.getElementById('appDialogMessage');
    const inputEl = document.getElementById('appDialogInput');
    const acceptButton = document.getElementById('appDialogAccept');
    const cancelButton = document.getElementById('appDialogCancel');
    if (!dialog || !titleEl || !messageEl || !inputEl || !acceptButton || !cancelButton) {
      return Promise.reject(new Error('Der Dialog konnte nicht geladen werden.'));
    }

    const showInput = options.showInput === true;
    const showCancel = options.showCancel === true || showInput;
    const variant = options.variant || 'info';
    titleEl.textContent = title;
    messageEl.textContent = message;
    dialog.dataset.variant = variant;
    inputEl.classList.toggle('hidden', !showInput);
    inputEl.type = options.inputType || 'text';
    inputEl.value = options.inputValue || '';
    acceptButton.textContent = options.acceptLabel || 'OK';
    cancelButton.textContent = options.cancelLabel || 'Abbrechen';
    cancelButton.classList.toggle('hidden', !showCancel);
    dialog.returnValue = '';

    return new Promise(resolve => {
      dialog.addEventListener('close', () => {
        const accepted = dialog.returnValue === 'accept';
        resolve(showInput ? (accepted ? inputEl.value : null) : accepted);
      }, { once: true });

      dialog.showModal();
      if (showInput) inputEl.focus();
      else acceptButton.focus();
    });
  }

  // --- Service Worker für 100% Offline-Betrieb ---

  registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js')
          .then((reg) => console.log('Service Worker aktiv:', reg.scope))
          .catch((err) => console.warn('Service Worker Fehler:', err));
      });
    }
  }

  // --- Lokale Speicherung auf dem Tablet ---

  loadPersistedState() {
    try {
      const savedConn = localStorage.getItem('leprendix_companion_conn');
      if (savedConn) {
        const parsed = JSON.parse(savedConn);
        if (parsed.host) this.connection.host = parsed.host;
        if (parsed.port) this.connection.port = parsed.port;
        if (parsed.token) this.connection.token = parsed.token;
      }

      const savedCfg = localStorage.getItem('leprendix_companion_config');
      if (savedCfg) {
        this.config = Object.assign(this.config, JSON.parse(savedCfg));
      }

      const savedRecords = localStorage.getItem('leprendix_companion_records');
      if (savedRecords) {
        this.localRecords = JSON.parse(savedRecords);
      }
    } catch (e) {
      console.warn('Fehler beim Laden lokaler Daten:', e);
    }
  }

  savePersistedState() {
    try {
      localStorage.setItem('leprendix_companion_conn', JSON.stringify({
        host: this.connection.host,
        port: this.connection.port,
        token: this.connection.token
      }));
      localStorage.setItem('leprendix_companion_config', JSON.stringify(this.config));
      localStorage.setItem('leprendix_companion_records', JSON.stringify(this.localRecords));
    } catch (e) {
      console.warn('Fehler beim Speichern lokaler Daten:', e);
    }
  }

  parseUrlParams() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('token')) this.connection.token = params.get('token');
    if (params.has('host')) this.connection.host = params.get('host');
    if (params.has('port')) this.connection.port = parseInt(params.get('port'), 10);
    this.savePersistedState();
  }

  initSignaturePad() {
    const canvas = document.getElementById('signatureCanvas');
    if (canvas) {
      this.signaturePad = new SignaturePad(canvas, {
        strokeStyle: '#1e293b',
        lineWidth: 4,
        onEnd: () => {
          this.validateCurrentStep();
          this.updateSignatureBadge();
        }
      });
    }
  }

  // --- Verbindungsprüfung ---

  getServerBaseUrl() {
    const portPart = this.connection.port ? `:${this.connection.port}` : '';
    const isNativeApp = window.Capacitor && window.Capacitor.isNativePlatform();
    const protocol = isNativeApp
      ? 'http:'
      : (window.location.protocol.startsWith('https') ? 'https:' : 'http:');
    return `${protocol}//${this.connection.host}${portPart}`;
  }

  async checkConnection(isBackground = false, syncContracts = true) {
    const statusDot = document.getElementById('connStatusDot');
    const statusText = document.getElementById('connStatusText');
    const dashConnDot = document.getElementById('dashConnDot');
    const dashConnText = document.getElementById('dashConnText');
    const adminStatusBox = document.getElementById('adminConnStatus');

    if (!this.connection.token) {
      this.updateConnectionBadges(false, 'Offline (Token fehlt)');
      return false;
    }

    try {
      const url = `${this.getServerBaseUrl()}/verify`;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: this.connection.token }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          this.connection.connected = true;
          this.connection.lastCheck = new Date();
          this.updateConnectionBadges(true, `Mit LeprendiX verbunden (${this.connection.host})`);
          if (syncContracts && Date.now() >= this.contractSyncRetryAt) {
            this.contractSyncRetryAt = Date.now() + 60000;
            try {
              await this.syncContractsFromServer();
            } catch (error) {
              console.warn('Verträge konnten nicht mit dem Praxis-PC synchronisiert werden:', error);
            }
          }
          return true;
        }
      }
    } catch (e) {
      // Nicht erreichbar
    }

    this.connection.connected = false;
    this.updateConnectionBadges(false, 'Offline-Modus');
    return false;
  }

  async syncContractsFromServer() {
    if (!this.connection.token) {
      throw new Error('Es ist kein Verbindungstoken gespeichert. Bitte zuerst den Praxis-PC verbinden.');
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);
    let response;
    try {
      response = await fetch(`${this.getServerBaseUrl()}/contracts`, {
        headers: { Authorization: `Bearer ${this.connection.token}` },
        cache: 'no-store',
        signal: controller.signal
      });
    } finally {
      clearTimeout(timeoutId);
    }
    if (!response.ok) {
      throw new Error(`Vertragsübertragung fehlgeschlagen (HTTP ${response.status}).`);
    }
    const data = await response.json();
    if (data.status !== 'ok' || !Array.isArray(data.contracts)) {
      throw new Error(data.message || 'Die Vertragsliste vom Praxis-PC ist ungültig.');
    }

    const enabledStates = new Map(
      this.contracts.contractsIndex.map(item => [item.id, item.enabled])
    );
    const mergedContracts = new Map(this.contracts.loadedContracts);
    let updatedCount = 0;
    for (const contract of data.contracts) {
      const current = mergedContracts.get(contract.id);
      const currentContent = current ? { ...current } : null;
      if (currentContent) delete currentContent.enabled;
      if (!currentContent || JSON.stringify(currentContent) !== JSON.stringify(contract)) {
        updatedCount++;
      }
      mergedContracts.set(contract.id, {
        ...contract,
        enabled: enabledStates.has(contract.id)
          ? enabledStates.get(contract.id)
          : contract.enabled
      });
    }
    if (data.contracts.length) {
      this.contracts.replaceContracts(Array.from(mergedContracts.values()));
      this.renderContractsInStep5();
      this.renderAdminContractsList();
      this.validateCurrentStep();
    }
    return {
      count: data.contracts.length,
      updatedCount,
      unchangedCount: data.contracts.length - updatedCount
    };
  }

  setupFirstRunWizard() {
    const chooseButton = document.getElementById('btnFirstRunChooseContracts');
    const fileInput = document.getElementById('firstRunContractFiles');
    const status = document.getElementById('firstRunContractStatus');
    const continueButton = document.getElementById('btnFirstRunContinue');
    const connectButton = document.getElementById('btnFirstRunConnect');
    const updateButton = document.getElementById('btnCheckAppUpdates');
    const adminChooseButton = document.getElementById('btnAdminImportContracts');
    const refreshContractsButton = document.getElementById('btnAdminRefreshContracts');
    const adminFileInput = document.getElementById('adminContractFiles');

    if (chooseButton && fileInput) {
      chooseButton.onclick = () => fileInput.click();
      fileInput.onchange = () => this.importContractFiles(fileInput, status);
    }
    if (adminChooseButton && adminFileInput) {
      adminChooseButton.onclick = () => adminFileInput.click();
      adminFileInput.onchange = () => this.importContractFiles(
        adminFileInput,
        document.getElementById('adminContractImportStatus')
      );
    }
    if (continueButton) {
      continueButton.onclick = () => {
        localStorage.setItem('leprendix_companion_setup_complete', 'true');
        document.getElementById('firstRunWizard')?.classList.add('hidden');
      };
    }
    if (connectButton) {
      connectButton.onclick = () => {
        document.getElementById('firstRunWizard')?.classList.add('hidden');
        this.openQrScanner();
      };
    }
    if (updateButton) {
      updateButton.onclick = () => this.checkForUpdatesMonthly(true, true);
    }
    if (refreshContractsButton) {
      refreshContractsButton.onclick = () => this.refreshContractsFromAdmin(refreshContractsButton);
    }
  }

  showFirstRunWizard() {
    if (localStorage.getItem('leprendix_companion_setup_complete') === 'true') return;
    const status = document.getElementById('firstRunContractStatus');
    if (status && this.contracts.getActiveContracts().length) {
      status.textContent = `${this.contracts.getActiveContracts().length} Vertragsdatei(en) sind lokal gespeichert.`;
    }
    document.getElementById('firstRunWizard')?.classList.remove('hidden');
  }

  async importContractFiles(input, statusElement) {
    const files = Array.from(input.files || []);
    if (!files.length) return;
    try {
      const count = await this.contracts.importFiles(files);
      if (statusElement) {
        statusElement.textContent = `${count} Vertrag/Verträge importiert und lokal gespeichert.`;
      }
      this.renderContractsInStep5();
      this.renderAdminContractsList();
      this.validateCurrentStep();
    } catch (error) {
      if (statusElement) statusElement.textContent = error.message;
      else await this.showAppDialog('Verträge', error.message, { variant: 'error' });
    } finally {
      input.value = '';
    }
  }

  async refreshContractsFromAdmin(button) {
    const status = document.getElementById('adminContractSyncStatus');
    const hostInput = document.getElementById('adminHostInput');
    const portInput = document.getElementById('adminPortInput');
    const tokenInput = document.getElementById('adminTokenInput');
    if (hostInput) this.connection.host = hostInput.value.trim();
    if (portInput) this.connection.port = parseInt(portInput.value.trim(), 10) || 5000;
    if (tokenInput) this.connection.token = tokenInput.value.trim();
    this.savePersistedState();

    button.disabled = true;
    button.textContent = 'Aktualisiere ...';
    if (status) status.textContent = 'Verbindung wird geprüft ...';
    try {
      const connected = await this.checkConnection(false, false);
      if (!connected) {
        throw new Error('Der Praxis-PC ist nicht erreichbar. Prüfen Sie WLAN, Host und Verbindungstoken.');
      }

      const result = await this.syncContractsFromServer();
      if (status) {
        status.textContent = result.count
          ? `${result.updatedCount} Vertrag/Verträge aktualisiert; ${result.unchangedCount} unverändert. Lokal: ${this.contracts.loadedContracts.size}.`
          : 'Der Praxis-PC hat keine Vertragsdateien bereitgestellt. Vorhandene lokale Verträge bleiben erhalten.';
      }
    } catch (error) {
      if (status) status.textContent = `Vertragsaktualisierung fehlgeschlagen: ${error.message}`;
      await this.showAppDialog(
        'Verträge aktualisieren',
        error.message,
        { variant: 'error' }
      );
    } finally {
      button.disabled = false;
      button.textContent = 'Verträge aktualisieren';
    }
  }

  async getInstalledVersion() {
    const response = await fetch('app-version.json', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error('Die installierte App-Version konnte nicht ermittelt werden.');
    }
    const data = await response.json();
    if (typeof data.version !== 'string' || !data.version.trim()) {
      throw new Error('Die Versionsdatei ist ungültig.');
    }
    return data.version.trim().replace(/^v/i, '');
  }

  compareVersions(left, right) {
    const leftParts = left.match(/\d+/g);
    const rightParts = right.match(/\d+/g);
    if (!leftParts || !rightParts) return 0;
    const length = Math.max(leftParts.length, rightParts.length);
    for (let index = 0; index < length; index++) {
      const leftPart = Number(leftParts[index] || 0);
      const rightPart = Number(rightParts[index] || 0);
      if (leftPart !== rightPart) return leftPart > rightPart ? 1 : -1;
    }
    return 0;
  }

  async checkForUpdatesMonthly(force = false, interactive = false) {
    const status = document.getElementById('appUpdateStatus');
    const lastCheck = Number(localStorage.getItem('leprendix_companion_last_update_check') || 0);
    if (!force && Date.now() - lastCheck < 30 * 24 * 60 * 60 * 1000) return;
    if (!window.Capacitor || !window.Capacitor.isNativePlatform()) {
      if (interactive) {
        document.getElementById('apkUpdateDownloadLink')?.classList.remove('hidden');
        if (status) {
          status.textContent = 'Automatische Versionsprüfung ist nur in der installierten Android-App verfügbar. Die neueste APK kann direkt geladen werden.';
        }
        await this.showAppDialog(
          'Companion aktualisieren',
          'Öffnen Sie den APK-Download auf GitHub und installieren Sie das Update über die Android-Abfrage. Deinstallieren Sie die vorhandene App nicht.',
          { variant: 'info' }
        );
      }
      return;
    }
    if (!navigator.onLine) {
      if (status) status.textContent = 'Offline. Die Update-Prüfung wird bei bestehender Internetverbindung wiederholt.';
      if (interactive) {
        await this.showAppDialog(
          'Update-Prüfung nicht möglich',
          'Für die Update-Prüfung wird eine Internetverbindung benötigt.',
          { variant: 'warning' }
        );
      }
      return;
    }

    if (status) status.textContent = 'Suche nach einer neueren Version ...';
    try {
      const installedVersion = await this.getInstalledVersion();
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      let releaseResponse;
      try {
        releaseResponse = await fetch('https://api.github.com/repos/qztq/LeprendiX/releases/latest', {
          headers: { Accept: 'application/vnd.github+json' },
          cache: 'no-store',
          signal: controller.signal
        });
      } finally {
        clearTimeout(timeoutId);
      }
      if (!releaseResponse.ok) {
        throw new Error(`GitHub-Updateprüfung fehlgeschlagen (HTTP ${releaseResponse.status}).`);
      }
      const release = await releaseResponse.json();
      const latestVersion = String(release.tag_name || '').replace(/^v/i, '');
      if (!latestVersion) throw new Error('Die neueste Release-Version fehlt.');

      localStorage.setItem('leprendix_companion_last_update_check', String(Date.now()));
      this.appVersion = installedVersion;
      if (status) status.textContent = `Installiert: ${installedVersion} · Aktuell: ${latestVersion}`;
      if (this.compareVersions(latestVersion, installedVersion) <= 0) {
        if (interactive) {
          await this.showAppDialog(
            'Companion ist aktuell',
            `Installierte Version: ${installedVersion}. Es ist kein Update verfügbar.`,
            { variant: 'success' }
          );
        }
        return;
      }
      document.getElementById('apkUpdateDownloadLink')?.classList.remove('hidden');

      const pendingCount = this.getUnsyncedRecords().length;
      const message = pendingCount
        ? `Version ${latestVersion} ist verfügbar. ${pendingCount} noch nicht synchronisierte Datensätze bleiben auf dem Tablet. Installieren Sie das Update über die Android-Abfrage, ohne die App vorher zu deinstallieren.`
        : `Version ${latestVersion} ist verfügbar. Installieren Sie das Update über die Android-Abfrage, ohne die App vorher zu deinstallieren.`;
      const accepted = await this.showAppDialog(
        'Companion-Update verfügbar',
        message,
        {
          showCancel: true,
          acceptLabel: 'APK herunterladen',
          cancelLabel: 'Später',
          variant: 'info'
        }
      );
      if (!accepted) return;

      this.savePersistedState();
      const browserPlugin = window.Capacitor?.Plugins?.Browser;
      if (browserPlugin?.open) {
        await browserPlugin.open({
          url: 'https://github.com/qztq/LeprendiX/releases/latest/download/LeprendiX_Mobile.apk'
        });
      } else {
        document.getElementById('apkUpdateDownloadLink')?.click();
      }
    } catch (error) {
      if (status) status.textContent = `Update-Prüfung nicht möglich: ${error.message}`;
      console.warn('Companion-Update-Prüfung fehlgeschlagen:', error);
      if (interactive) {
        await this.showAppDialog(
          'Update-Prüfung fehlgeschlagen',
          error.message,
          { variant: 'error' }
        );
      }
    }
  }

  updateConnectionBadges(isConnected, label) {
    const dots = [document.getElementById('connStatusDot'), document.getElementById('dashConnDot')];
    const texts = [document.getElementById('connStatusText'), document.getElementById('dashConnText')];
    const adminBox = document.getElementById('adminConnStatus');

    dots.forEach(dot => {
      if (dot) dot.className = `status-dot ${isConnected ? 'connected' : 'disconnected'}`;
    });
    texts.forEach(txt => {
      if (txt) txt.textContent = label;
    });

    if (adminBox) {
      adminBox.className = `status-badge ${isConnected ? 'success' : 'neutral'}`;
      adminBox.textContent = isConnected ? `Verbunden (${this.connection.host}:${this.connection.port})` : 'Offline';
    }
  }

  // --- Punkt 1: Dashboard Logik & Ansichten-Steuerung ---

  switchView(mode) {
    this.currentMode = mode;
    const dashView = document.getElementById('dashboardView');
    const patientView = document.getElementById('patientView');
    const adminView = document.getElementById('adminView');
    const keyboard = document.getElementById('customVirtualKeyboard');

    if (dashView) dashView.classList.toggle('hidden', mode !== 'dashboard');
    if (patientView) patientView.classList.toggle('hidden', mode !== 'patient');
    if (adminView) adminView.classList.toggle('hidden', mode !== 'admin');

    // Tastatur nur im Patienten-Wizard anzeigen falls Eingabefeld aktiv
    if (mode !== 'patient' && keyboard) {
      keyboard.classList.add('hidden');
    }

    if (mode === 'dashboard') {
      this.updateDashboardStats();
    } else if (mode === 'admin') {
      this.populateAdminData();
    }
  }

  getUnsyncedRecords() {
    return this.localRecords.filter(r => !r.synced);
  }

  getSyncedRecords() {
    return this.localRecords.filter(r => r.synced);
  }

  updateDashboardStats() {
    const totalCount = this.localRecords.length;
    const syncedCount = this.getSyncedRecords().length;
    const pendingCount = this.getUnsyncedRecords().length;

    const countTotalEl = document.getElementById('dashCountTotal');
    const countSyncedEl = document.getElementById('dashCountSynced');
    const countPendingEl = document.getElementById('dashCountPending');
    const btnSync = document.getElementById('btnDashSync');
    const syncSubtext = document.getElementById('dashSyncSubtext');

    if (countTotalEl) countTotalEl.textContent = totalCount;
    if (countSyncedEl) countSyncedEl.textContent = syncedCount;
    if (countPendingEl) countPendingEl.textContent = pendingCount;

    if (syncSubtext) {
      syncSubtext.textContent = pendingCount > 0 
        ? `${pendingCount} Datensätze warten auf Monats-Sync`
        : `Alle ${syncedCount} Datensätze bereits synchronisiert`;
    }

    // Tabelle der zuletzt erfassten Patienten im Dashboard
    const tbody = document.getElementById('dashRecentTbody');
    if (tbody) {
      tbody.innerHTML = '';
      if (totalCount === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Noch keine Patienten erfasst. Tippen Sie auf "Neuen Patienten erfassen".</td></tr>';
      } else {
        const recent = this.localRecords.slice(-5).reverse();
        recent.forEach(r => {
          const p = r.patient;
          const tr = document.createElement('tr');
          const badge = r.synced 
            ? `<span class="status-badge success">Synchronisiert</span>`
            : `<span class="status-badge warning">Ausstehend</span>`;
          tr.innerHTML = `
            <td>${r.readableDate || '—'}</td>
            <td><strong>${p.anrede || ''} ${p.vorname} ${p.nachname}</strong></td>
            <td><code>${p.vsnr || '—'}</code></td>
            <td>${p.plz} ${p.ort}</td>
            <td>${badge}</td>
          `;
          tbody.appendChild(tr);
        });
      }
    }
  }

  // --- Punkt 4: Titel zur Anrede dazu (z. B. "Herr Dr.") ---

  getAllTitles() {
    return this.formData.titel.filter(Boolean);
  }

  /**
   * Bildet die vollständige Anrede inklusive aller gewählten Titel.
   * Beispiel: "Herr" + ["Dr.", "med."] => "Herr Dr. med."
   */
  getFormattedAnredeWithTitles() {
    const titlesStr = this.getAllTitles().join(' ').trim();
    const baseAnrede = this.formData.anrede || 'Herr/Frau';
    if (titlesStr) {
      return `${baseAnrede} ${titlesStr}`.trim();
    }
    return baseAnrede;
  }

  updateSummaryCard() {
    const nameEl = document.getElementById('summaryLiveName');
    const anredeEl = document.getElementById('summaryLiveAnrede');
    const svnrEl = document.getElementById('summaryLiveSvnr');
    const addressEl = document.getElementById('summaryLiveAddress');

    const formattedAnrede = this.getFormattedAnredeWithTitles();
    const fullName = `${this.formData.vorname} ${this.formData.nachname}`.trim();

    if (anredeEl) anredeEl.textContent = formattedAnrede;
    if (nameEl) nameEl.textContent = fullName || 'Noch kein Name';

    const svnr = (this.formData.vsnrNummer + ' ' + this.formData.vsnrGeburtsdatum).trim();
    if (svnrEl) svnrEl.textContent = svnr || '—';

    const addr = `${this.formData.strasse} ${this.formData.hausnummer} ${this.formData.plz} ${this.formData.ort}`.trim();
    if (addressEl) addressEl.textContent = addr || '—';
  }

  // --- Punkt 1: Eigene, integrierte Bildschirmtastatur ---

  setupCustomKeyboard() {
    const btnSymbols = document.getElementById('btnKeyboardToggleSymbols');
    const btnClose = document.getElementById('btnKeyboardClose');

    if (btnSymbols) {
      btnSymbols.onclick = () => {
        this.keyboardMode = (this.keyboardMode === 'letters') ? 'symbols' : 'letters';
        btnSymbols.textContent = (this.keyboardMode === 'letters') ? '?123' : 'ABC';
        this.renderKeyboardKeys();
      };
    }

    if (btnClose) {
      btnClose.onclick = () => this.closeKeyboard();
    }

    // Alle Eingabefelder mit der virtuellen Tastatur verknüpfen
    document.querySelectorAll('.use-virtual-keyboard').forEach(input => {
      // Verhindert das Aufpoppen der nativen Systemtastatur
      input.setAttribute('inputmode', 'none');
      input.setAttribute('autocomplete', 'off');

      input.onfocus = () => this.activateKeyboardForInput(input);
      input.onclick = () => this.activateKeyboardForInput(input);
    });
  }

  activateKeyboardForInput(input) {
    this.activeKeyboardInput = input;
    document.querySelectorAll('.use-virtual-keyboard').forEach(i => i.classList.remove('active-virtual-keyboard-input'));
    input.classList.add('active-virtual-keyboard-input');

    const keyboardEl = document.getElementById('customVirtualKeyboard');
    if (keyboardEl) keyboardEl.classList.remove('hidden');

    // Label in Toolbar
    const fieldLabel = document.getElementById('activeKeyboardFieldLabel');
    if (fieldLabel) {
      const placeholder = input.getAttribute('placeholder') || input.id;
      fieldLabel.textContent = `Eingabe: ${input.labels && input.labels[0] ? input.labels[0].textContent.replace('*', '').trim() : placeholder}`;
    }

    // Wenn Feld leer ist, Anfangsbuchstaben groß schreiben
    this.isShifted = (input.value.length === 0);
    this.keyboardMode = ['inputPlz', 'inputHausnummer'].includes(input.id)
      ? 'numeric'
      : 'letters';
    if (keyboardEl) {
      keyboardEl.classList.toggle('numeric-keyboard', this.keyboardMode === 'numeric');
    }
    const btnSymbols = document.getElementById('btnKeyboardToggleSymbols');
    if (btnSymbols) {
      btnSymbols.classList.toggle('hidden', this.keyboardMode === 'numeric');
      btnSymbols.textContent = '?123';
    }

    this.renderKeyboardKeys();
  }

  renderKeyboardKeys() {
    const container = document.getElementById('keyboardKeysGrid');
    if (!container) return;
    container.innerHTML = '';

    let rows = [];

    if (this.keyboardMode === 'numeric') {
      rows = [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['clear', '0', 'backspace'],
        ['next']
      ];
    } else if (this.keyboardMode === 'letters') {
      const r1 = ['q', 'w', 'e', 'r', 't', 'z', 'u', 'i', 'o', 'p', 'ü'];
      const r2 = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'ö', 'ä'];
      const r3 = ['shift', 'y', 'x', 'c', 'v', 'b', 'n', 'm', 'ß', 'backspace'];
      const r4 = ['space', '-', '.', '/', 'clear', 'next'];
      rows = [r1, r2, r3, r4];
    } else {
      const r1 = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'];
      const r2 = ['+', '-', '*', '/', '=', '%', '&', '€', '$', '@'];
      const r3 = ['(', ')', '[', ']', '{', '}', '<', '>', '!', 'backspace'];
      const r4 = ['space', ',', '.', ':', ';', 'clear', 'next'];
      rows = [r1, r2, r3, r4];
    }

    rows.forEach(rowKeys => {
      const rowDiv = document.createElement('div');
      rowDiv.className = 'kb-row';

      rowKeys.forEach(k => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'kb-key';

        if (k === 'shift') {
          btn.classList.add('shift-key');
          if (this.isShifted) btn.classList.add('active');
          btn.textContent = 'Umschalt';
          btn.onclick = () => {
            this.isShifted = !this.isShifted;
            this.renderKeyboardKeys();
          };
        } else if (k === 'backspace') {
          btn.classList.add('backspace-key');
          btn.textContent = 'Löschen';
          btn.onclick = () => this.handleKeyboardKey('backspace');
        } else if (k === 'space') {
          btn.classList.add('space-key');
          btn.textContent = 'Leerzeichen';
          btn.onclick = () => this.handleKeyboardKey(' ');
        } else if (k === 'clear') {
          btn.classList.add('clear-key');
          btn.textContent = 'Löschen';
          btn.title = 'Feld leeren';
          btn.onclick = () => this.handleKeyboardKey('clear');
        } else if (k === 'next') {
          btn.classList.add('next-key');
          btn.textContent = 'Weiter';
          btn.onclick = () => this.advanceToNextInputField();
        } else {
          const char = this.keyboardMode === 'numeric'
            ? k
            : (this.isShifted ? k.toUpperCase() : k.toLowerCase());
          btn.textContent = char;
          btn.onclick = () => this.handleKeyboardKey(char);
        }

        rowDiv.appendChild(btn);
      });

      container.appendChild(rowDiv);
    });
  }

  handleKeyboardKey(val) {
    if (!this.activeKeyboardInput) return;

    const input = this.activeKeyboardInput;
    let text = input.value;

    if (val === 'backspace') {
      input.value = text.slice(0, -1);
    } else if (val === 'clear') {
      input.value = '';
    } else {
      if (
        this.keyboardMode === 'numeric' &&
        input.maxLength > 0 &&
        text.length >= input.maxLength
      ) {
        return;
      }
      input.value = text + val;
      // Nach Großbuchstabe automatisch auf Kleinbuchstaben umschalten
      if (this.isShifted && this.keyboardMode === 'letters') {
        this.isShifted = false;
        this.renderKeyboardKeys();
      }
    }

    // Input-Event feuern, damit Validierung und Live-Summary reagieren
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  advanceToNextInputField() {
    const inputs = Array.from(document.querySelectorAll('.step-pane:not(.hidden) .use-virtual-keyboard'));
    if (!inputs.length) return;

    const currentIdx = inputs.indexOf(this.activeKeyboardInput);
    if (currentIdx !== -1 && currentIdx < inputs.length - 1) {
      // Move to next field in same step
      inputs[currentIdx + 1].focus();
    } else {
      // Last field in step → close keyboard and go to next step
      this.closeKeyboard();
      this.validateCurrentStep();
      const btnNext = document.getElementById('btnStepNext');
      if (btnNext && !btnNext.disabled) {
        btnNext.click();
      }
    }
  }

  closeKeyboard() {
    const keyboardEl = document.getElementById('customVirtualKeyboard');
    if (keyboardEl) keyboardEl.classList.add('hidden');
    if (this.activeKeyboardInput) {
      this.activeKeyboardInput.classList.remove('active-virtual-keyboard-input');
    }
    this.activeKeyboardInput = null;
  }

  // --- Punkt 2: Pre-Sync Review (Hausbesuch, Distanz, Kilometergeld) ---

  async openSyncReview() {
    const unsynced = this.getUnsyncedRecords();
    if (unsynced.length === 0) {
      await this.showAppDialog(
        'Alles synchronisiert',
        'Alle Patientendaten sind bereits synchronisiert. Es gibt keine ausstehenden Daten.',
        { variant: 'success' }
      );
      return;
    }

    const reviewModal = document.getElementById('syncReviewView');
    const reviewList = document.getElementById('syncReviewList');
    const summaryText = document.getElementById('syncReviewSummaryText');

    if (!reviewModal || !reviewList) return;

    reviewList.innerHTML = '<div class="text-center text-muted" style="padding: 20px;">Berechne Entfernungen und bereite Prüfung vor...</div>';
    reviewModal.classList.remove('hidden');

    if (summaryText) {
      summaryText.textContent = `${unsynced.length} Patient(en) zur Überprüfung bereit`;
    }

    // Karten für jeden Patienten rendern
    reviewList.innerHTML = '';
    for (let idx = 0; idx < unsynced.length; idx++) {
      const rec = unsynced[idx];
      const p = rec.patient;
      const card = document.createElement('div');
      card.className = 'sync-patient-card';

      const fullAddress = `${p.strasse} ${p.hausnummer}, ${p.plz} ${p.ort}`;
      const defaultKm = (p.kilometergeld !== undefined && p.kilometergeld !== null) ? p.kilometergeld : '0.00';
      const isHausbesuch = (p.is_hausbesuch !== undefined) ? p.is_hausbesuch : false;

      card.innerHTML = `
        <div class="sync-patient-header">
          <div>
            <h4>${p.anrede || ''} ${p.vorname} ${p.nachname}</h4>
            <span class="text-muted" style="font-size: 13px;">SVNr: <code>${p.vsnr || '—'}</code> | ${fullAddress}</span>
          </div>
          <span class="badge ${isHausbesuch ? 'badge-required' : 'badge-optional'}">
            ${isHausbesuch ? 'Hausbesuch' : 'Ordination'}
          </span>
        </div>

        <div class="sync-review-controls-grid">
          <!-- Hausbesuch Toggle -->
          <div class="hausbesuch-toggle-box">
            <label style="font-size: 13px; font-weight: 600;">Hausbesuch durchgeführt?</label>
            <button type="button" class="hausbesuch-btn ${isHausbesuch ? 'active' : ''}" data-idx="${idx}">
              <span>${isHausbesuch ? 'Ja, Hausbesuch' : 'Nein, in Ordination'}</span>
            </button>
          </div>

          <!-- Distanz-Anzeige (Punkt 2) -->
          <div class="distance-badge-box">
            <label style="font-size: 12px; font-weight: 600; color: var(--text-muted);">Entfernung ab Ordination:</label>
            <div>
              <span class="distance-pill" id="distPill_${idx}">
                Distanz wird ermittelt...
              </span>
            </div>
          </div>

          <!-- Kilometergeld Betrag (Punkt 2) -->
          <div class="km-geld-input-box">
            <label for="kmInput_${idx}">Kilometergeld (€):</label>
            <input type="number" step="0.01" min="0" id="kmInput_${idx}" class="input-touch" style="height: 40px; font-size: 15px;" value="${parseFloat(defaultKm).toFixed(2)}" ${!isHausbesuch ? 'disabled' : ''}>
          </div>
        </div>
      `;

      // Event-Handler für Hausbesuch Toggle
      const hbBtn = card.querySelector('.hausbesuch-btn');
      const kmInput = card.querySelector(`#kmInput_${idx}`);
      const distPill = card.querySelector(`#distPill_${idx}`);

      hbBtn.onclick = () => {
        const currentlyActive = hbBtn.classList.contains('active');
        const nextActive = !currentlyActive;
        hbBtn.classList.toggle('active', nextActive);
        hbBtn.innerHTML = `<span>${nextActive ? 'Ja, Hausbesuch' : 'Nein, in Ordination'}</span>`;
        card.querySelector('.badge').textContent = nextActive ? 'Hausbesuch' : 'Ordination';
        card.querySelector('.badge').className = `badge ${nextActive ? 'badge-required' : 'badge-optional'}`;

        p.is_hausbesuch = nextActive;
        if (kmInput) {
          kmInput.disabled = !nextActive;
          if (nextActive) {
            // Vorschlag berechnen falls vorhanden
            const suggested = distPill.dataset.suggested;
            if (suggested) kmInput.value = suggested;
            kmInput.focus();
          } else {
            kmInput.value = '0.00';
          }
          p.kilometergeld = parseFloat(kmInput.value || 0);
        }
        this.savePersistedState();
      };

      if (kmInput) {
        kmInput.oninput = (e) => {
          p.kilometergeld = parseFloat(e.target.value || 0);
          this.savePersistedState();
        };
      }

      reviewList.appendChild(card);

      // Asynchron Distanz abrufen via mobile_connect.py /calculate_distance
      this.fetchDistanceForPatient(fullAddress, idx);
    }
  }

  async fetchDistanceForPatient(address, idx) {
    const pill = document.getElementById(`distPill_${idx}`);
    if (!pill) return;

    try {
      if (this.connection.connected) {
        const res = await fetch(`${this.getServerBaseUrl()}/calculate_distance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ address: address })
        });
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'ok' && data.distance_km > 0) {
            pill.innerHTML = `ca. <strong>${data.distance_km} km</strong> (Hin- & Rückfahrt ca. ${(data.distance_km * 2).toFixed(1)} km)`;
            pill.dataset.suggested = (data.suggested_km_geld || (data.distance_km * 2)).toFixed(2);
            return;
          }
        }
      }
    } catch (e) {
      // Fallback
    }

    pill.innerHTML = `Ordination Wiener Neudorf`;
    pill.dataset.suggested = '0.00';
  }

  // --- Punkt 3: Ladebalken & Senden der Daten ---

  async executeBatchSync() {
    const unsynced = this.getUnsyncedRecords();
    if (unsynced.length === 0) return;

    const progressModal = document.getElementById('syncProgressModal');
    const barFill = document.getElementById('progressBarFill');
    const percentText = document.getElementById('progressPercentText');
    const actionText = document.getElementById('progressCurrentAction');
    const subTitle = document.getElementById('progressSubTitle');

    if (progressModal) progressModal.classList.remove('hidden');

    const updateProgress = (percent, action) => {
      if (barFill) barFill.style.width = `${percent}%`;
      if (percentText) percentText.textContent = `${percent}%`;
      if (actionText) actionText.textContent = action;
    };

    updateProgress(10, 'Prüfe WLAN-Verbindung zu LeprendiX...');

    try {
      const isConnected = await this.checkConnection();
      if (!isConnected) {
        throw new Error('LeprendiX ist nicht erreichbar. Bitte stellen Sie sicher, dass das Programm läuft.');
      }

      updateProgress(30, `${unsynced.length} Patient(en) werden vorbereitet...`);

      const batchPayload = {
        token: this.connection.token,
        records: unsynced.map(r => ({
          id: r.id,
          patient: {
            ...r.patient,
            anrede: r.patient.anrede, // Beinhaltet Titel (Punkt 4)
            kilometergeld: r.patient.kilometergeld || 0.0,
            is_hausbesuch: !!r.patient.is_hausbesuch
          },
          contracts: r.contracts,
          signature: r.signature
        }))
      };

      updateProgress(60, 'Übertrage Daten an LeprendiX...');

      const res = await fetch(`${this.getServerBaseUrl()}/sync_batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(batchPayload)
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.message || `Server meldet Fehler ${res.status}`);
      }

      updateProgress(90, 'Warte auf Stammdaten-Eingabe für alle Patienten...');

      if (result.status === 'success') {
        const syncedIds = new Set(result.synced_ids || []);
        if (!unsynced.every(record => syncedIds.has(record.id))) {
          throw new Error(
            'LeprendiX hat nicht alle Patienten als vollständig bearbeitet bestätigt. '
            + 'Die Datensätze bleiben aus Sicherheitsgründen ausstehend.'
          );
        }
        const nowIso = new Date().toISOString();

        this.localRecords.forEach(r => {
          if (syncedIds.has(r.id)) {
            r.synced = true;
            r.syncedAt = nowIso;
          }
        });

        this.savePersistedState();
        updateProgress(100, 'Erfolgreich synchronisiert!');

        setTimeout(async () => {
          if (progressModal) progressModal.classList.add('hidden');
          const reviewModal = document.getElementById('syncReviewView');
          if (reviewModal) reviewModal.classList.add('hidden');

          this.updateDashboardStats();
          this.switchView('dashboard');

          await this.showAppDialog(
            'Synchronisation abgeschlossen',
            `${result.imported} neue Patienten wurden angelegt; ${result.reactivated || 0} archivierte Patienten wurden reaktiviert. Am Praxis-PC können jetzt Stammdaten-Leistungen verwaltet werden; es wurden keine Behandlungen angelegt.`,
            { variant: 'success' }
          );
        }, 800);
      } else {
        throw new Error(result.message || 'Unbekannter Fehler bei der Synchronisation.');
      }

    } catch (err) {
      if (progressModal) progressModal.classList.add('hidden');
      await this.showAppDialog(
        'Synchronisation fehlgeschlagen',
        err.message,
        { variant: 'error' }
      );
    }
  }

  // --- QR-Code Scanner mit Tablet-Kamera ---

  async openQrScanner() {
    const modal = document.getElementById('qrScannerModal');
    const video = document.getElementById('qrVideoFeed');
    if (!modal || !video) return;

    modal.classList.remove('hidden');

    try {
      this.qrStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      video.srcObject = this.qrStream;
      await video.play();

      // BarcodeDetector API falls unterstützt
      if ('BarcodeDetector' in window) {
        const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
        this.qrScanInterval = setInterval(async () => {
          try {
            const barcodes = await detector.detect(video);
            if (barcodes.length > 0) {
              const rawValue = barcodes[0].rawValue;
              this.handleQrScanResult(rawValue);
            }
          } catch (e) {}
        }, 300);
      }
    } catch (err) {
      console.warn('Kamera konnte nicht gestartet werden:', err);
    }
  }

  closeQrScanner() {
    const modal = document.getElementById('qrScannerModal');
    if (modal) modal.classList.add('hidden');

    if (this.qrScanInterval) {
      clearInterval(this.qrScanInterval);
      this.qrScanInterval = null;
    }

    if (this.qrStream) {
      this.qrStream.getTracks().forEach(t => t.stop());
      this.qrStream = null;
    }
  }

  async handleQrScanResult(qrText) {
    if (!qrText) return;
    this.closeQrScanner();

    // Format: http://<ip>:<port>/?token=<token> oder IP:PORT|TOKEN
    try {
      if (qrText.includes('token=')) {
        const url = new URL(qrText);
        this.connection.host = url.hostname;
        this.connection.port = url.port ? parseInt(url.port, 10) : 5000;
        this.connection.token = url.searchParams.get('token');
      } else if (qrText.includes('|')) {
        const [hostPort, token] = qrText.split('|');
        const [host, port] = hostPort.split(':');
        if (!host || !token) throw new Error('Host oder Token fehlt.');
        this.connection.host = host;
        this.connection.port = parseInt(port, 10) || 5000;
        this.connection.token = token;
      } else {
        throw new Error('Das QR-Code-Format wird nicht erkannt.');
      }
      if (!this.connection.host || !this.connection.token) {
        throw new Error('Host oder Token fehlt.');
      }
      this.savePersistedState();
      const connected = await this.checkConnection();
      if (connected && this.contracts.getActiveContracts().length) {
        localStorage.setItem('leprendix_companion_setup_complete', 'true');
      }
      await this.showAppDialog(
        connected ? 'Verbindung erfolgreich' : 'Verbindung nicht möglich',
        connected
          ? 'Der QR-Code wurde erfolgreich gescannt. Verträge wurden, falls vorhanden, lokal gespeichert.'
          : 'Der QR-Code wurde gelesen, aber der Praxis-PC ist derzeit nicht erreichbar.',
        { variant: connected ? 'success' : 'warning' }
      );
    } catch (e) {
      await this.showAppDialog(
        'Ungültiger QR-Code',
        `Der QR-Code konnte nicht verarbeitet werden: ${e.message}`,
        { variant: 'error' }
      );
    }
  }

  // --- Step Rendering im Wizard ---

  renderStep(stepNumber) {
    this.currentStep = stepNumber;

    document.querySelectorAll('.step-pane').forEach(pane => pane.classList.add('hidden'));

    const activePane = document.getElementById(`stepPane${stepNumber}`);
    if (activePane) activePane.classList.remove('hidden');

    document.querySelectorAll('.stepper-item').forEach(item => {
      const stepIdx = parseInt(item.dataset.step, 10);
      item.classList.remove('active', 'completed');
      if (stepIdx === stepNumber) item.classList.add('active');
      else if (stepIdx < stepNumber) item.classList.add('completed');
    });

    const btnBack = document.getElementById('btnStepBack');
    const btnNext = document.getElementById('btnStepNext');
    const footerNav = document.getElementById('patientFooterNav');
    if (btnNext) btnNext.style.display = stepNumber === 6 ? 'none' : 'inline-flex';
    if (footerNav) footerNav.style.display = stepNumber < 7 ? 'flex' : 'none';

    if (stepNumber === 1) {
      if (btnBack) btnBack.style.visibility = 'hidden';
      if (btnNext) btnNext.textContent = 'Weiter zu Name';
    } else if (stepNumber === 5) {
      if (btnBack) btnBack.style.visibility = 'visible';
      if (btnNext) btnNext.textContent = 'Weiter zur Übersicht';
      this.renderContractsInStep5();
      setTimeout(() => {
        if (this.signaturePad) this.signaturePad.resizeCanvas();
      }, 50);
    } else if (stepNumber === 6) {
      if (btnBack) btnBack.style.visibility = 'visible';
      if (btnNext) btnNext.style.display = 'none';
      this.renderStep6Summary();
    } else if (stepNumber === 7) {
      if (footerNav) footerNav.style.display = 'none';
    } else {
      if (btnBack) btnBack.style.visibility = 'visible';
      if (btnNext) {
        btnNext.style.display = 'inline-flex';
        btnNext.textContent = 'Weiter';
      }
    }

    // Virtuelle Tastatur für das erste Eingabefeld im Schritt fokussieren
    const firstInput = activePane ? activePane.querySelector('.use-virtual-keyboard') : null;
    if (firstInput && (stepNumber === 2 || stepNumber === 4)) {
      setTimeout(() => this.activateKeyboardForInput(firstInput), 100);
    }

    this.validateCurrentStep();
  }

  validateCurrentStep() {
    const btnNext = document.getElementById('btnStepNext');
    if (!btnNext) return;

    let isValid = false;
    switch (this.currentStep) {
      case 1:
        isValid = !!this.formData.anrede;
        break;
      case 2:
        isValid = this.formData.vorname.trim().length > 0 && this.formData.nachname.trim().length > 0;
        break;
      case 3:
        isValid = (this.formData.vsnrNummer.length === 4 && this.formData.vsnrGeburtsdatum.length === 6);
        break;
      case 4:
        isValid = this.formData.strasse.trim().length > 0 &&
                  this.formData.hausnummer.trim().length > 0 &&
                  this.formData.plz.trim().length >= 4 &&
                  this.formData.ort.trim().length > 0 &&
                  this.formData.krankenkasse.trim().length > 0;
        break;
      case 5:
        const contractsConsent = this.contracts.areAllRequiredConsented();
        const hasSignature = this.signaturePad && !this.signaturePad.isEmpty();
        isValid = this.contracts.getActiveContracts().length > 0 &&
                  contractsConsent &&
                  hasSignature;
        break;
      case 6:
        isValid = true;
        break;
      default:
        isValid = true;
    }

    btnNext.disabled = !isValid;
  }

  goToNextStep() {
    if (this.currentStep < this.totalSteps) {
      this.closeKeyboard();
      this.renderStep(this.currentStep + 1);
    }
  }

  goToPrevStep() {
    if (this.currentStep > 1) {
      this.closeKeyboard();
      this.renderStep(this.currentStep - 1);
    }
  }

  // --- Step 5 & 6 Rendering ---

  escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[character]);
  }

  renderContractsInStep5() {
    const container = document.getElementById('contractsListContainer');
    if (!container) return;
    container.innerHTML = '';

    const activeContracts = this.contracts.getActiveContracts();
    if (!activeContracts.length) {
      const emptyState = document.createElement('p');
      emptyState.className = 'text-muted';
      emptyState.textContent = 'Noch keine Vertragsdateien geladen. Verbinden Sie das Tablet mit dem Praxis-PC oder importieren Sie JSON-Dateien im Startassistenten.';
      container.appendChild(emptyState);
    }

    activeContracts.forEach(contractItem => {
      const contract = this.contracts.getContract(contractItem.id);
      if (!contract) return;

      const card = document.createElement('div');
      card.className = 'contract-card';

      card.innerHTML = `
        <div class="contract-header">
          <div>
            <h3>${this.escapeHtml(contract.title)}</h3>
            <p class="contract-subtitle">${this.escapeHtml(contract.subtitle || '')}</p>
          </div>
          <span class="badge ${contractItem.required ? 'badge-required' : 'badge-optional'}">
            ${this.escapeHtml(contractItem.badge || (contractItem.required ? 'Pflicht' : 'Optional'))}
          </span>
        </div>
        <div class="contract-body-scroll">
          ${(contract.sections || []).map(section =>
            `<h4>${this.escapeHtml(section.heading)}</h4><p>${this.escapeHtml(section.text).replace(/\n/g, '<br>')}</p>`
          ).join('')}
        </div>
      `;

      if (contract.checkboxes && contract.checkboxes.length > 0) {
        const checkboxGroup = document.createElement('div');
        checkboxGroup.className = 'contract-checkbox-group';

        contract.checkboxes.forEach(cb => {
          const row = document.createElement('label');
          row.className = 'custom-checkbox-row';
          const isChecked = this.contracts.getCheckboxState(contract.id, cb.id);

          row.innerHTML = `
            <input type="checkbox" class="consent-checkbox" data-contract="${this.escapeHtml(contract.id)}" data-id="${this.escapeHtml(cb.id)}" ${isChecked ? 'checked' : ''}>
            <span>${this.escapeHtml(cb.label)} ${cb.required ? '<span class="text-danger">*</span>' : ''}</span>
          `;

          row.querySelector('input').onchange = (e) => {
            this.contracts.setCheckboxState(contract.id, cb.id, e.target.checked);
            this.validateCurrentStep();
          };

          checkboxGroup.appendChild(row);
        });
        card.appendChild(checkboxGroup);
      }

      container.appendChild(card);
    });

    const sigLabel = document.getElementById('signaturePatientLabel');
    if (sigLabel) {
      const formattedAnrede = this.getFormattedAnredeWithTitles();
      sigLabel.textContent = `Unterschrift von: ${formattedAnrede} ${this.formData.vorname} ${this.formData.nachname}`.trim();
    }
  }

  updateSignatureBadge() {
    const badge = document.getElementById('signatureStatusBadge');
    if (!badge) return;
    if (this.signaturePad && !this.signaturePad.isEmpty()) {
      badge.className = 'status-badge success';
      badge.textContent = 'Unterschrift erfasst';
    } else {
      badge.className = 'status-badge neutral';
      badge.textContent = 'Bitte hier im Feld unterschreiben';
    }
  }

  renderStep6Summary() {
    const summaryContainer = document.getElementById('finalSummaryCard');
    if (!summaryContainer) return;

    const formattedAnrede = this.getFormattedAnredeWithTitles();
    const fullSvnr = this.formData.vsnrFull || `${this.formData.vsnrNummer}${this.formData.vsnrGeburtsdatum}`;
    const sigDataUrl = this.signaturePad ? this.signaturePad.toDataURL() : null;
    const today = new Date().toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit', year: 'numeric' });

    const fullAddress = [
      `${this.formData.strasse} ${this.formData.hausnummer}`.trim(),
      this.formData.adresszusatz || '',
      `${this.formData.plz} ${this.formData.ort}`.trim()
    ].filter(Boolean).join(', ');

    // Build the signed contract preview (matching the actual Wundpraxis Mödling form)
    const activeContracts = this.contracts.getActiveContracts();
    const contractSections = activeContracts.map(contractItem => {
      const contract = this.contracts.getContract(contractItem.id);
      if (!contract) return '';
      const checkboxSummary = (contract.checkboxes || []).map(cb => {
        const accepted = this.contracts.getCheckboxState(contract.id, cb.id);
        return `<li class="${accepted ? 'consent-accepted' : 'consent-declined'}">
          ${accepted ? 'Zugestimmt' : 'Nicht ausgewählt'}: ${this.escapeHtml(cb.label)}
        </li>`;
      }).join('');
      return `
        <div class="contract-preview-section">
          <h4 class="contract-preview-title">${this.escapeHtml(contract.title)}</h4>
          ${(contract.sections || []).map(s =>
            `<div class="contract-preview-block">
              <strong>${this.escapeHtml(s.heading)}</strong>
              <p>${this.escapeHtml(s.text).replace(/\n/g, '<br>')}</p>
            </div>`
          ).join('')}
          <div class="contract-preview-consents">
            <strong>Auswahl:</strong>
            <ul>${checkboxSummary || '<li>Keine Auswahlfelder</li>'}</ul>
          </div>
        </div>`;
    }).join('');

    summaryContainer.innerHTML = `
      <!-- Printable contract document -->
      <div class="contract-print-document">
        <div class="contract-print-header">
          <h3>Einwilligungserklärung</h3>
          <span class="text-muted" style="font-size:13px;">Wundpraxis Mödling · Birgit Hager · Bahnstraße 2/1/2, 2351 Wiener Neudorf</span>
        </div>

        <div class="contract-print-patientinfo">
          <div class="contract-print-field">
            <span class="field-label">Anrede:</span>
            <span class="field-value">${this.formData.anrede || '—'}</span>
          </div>
          <div class="contract-print-field">
            <span class="field-label">Titel:</span>
            <span class="field-value">${this.getAllTitles().join(' ') || '—'}</span>
          </div>
          <div class="contract-print-field">
            <span class="field-label">Name:</span>
            <span class="field-value">${this.formData.vorname} ${this.formData.nachname}</span>
          </div>
          <div class="contract-print-field">
            <span class="field-label">Adresse:</span>
            <span class="field-value">${fullAddress || '—'}</span>
          </div>
          <div class="contract-print-field">
            <span class="field-label">SV-Nummer:</span>
            <span class="field-value field-mono">${fullSvnr || '—'}</span>
          </div>
          <div class="contract-print-field">
            <span class="field-label">Krankenkasse:</span>
            <span class="field-value">${this.formData.krankenkasse || '—'}</span>
          </div>
        </div>

        <div class="contract-print-body">
          ${contractSections}
        </div>

        <div class="contract-print-signature">
          <div class="sig-date-row">
            <div class="sig-date-box">
              <span class="field-label">Datum:</span>
              <span class="field-value" style="font-size: 16px; font-weight: 700;">${today}</span>
            </div>
            <div class="sig-box">
              <span class="field-label">Unterschrift:</span>
              ${sigDataUrl ? `<img src="${sigDataUrl}" alt="Unterschrift" class="sig-preview-img" />` : '<span class="text-danger" style="font-size:13px;">Keine Unterschrift</span>'}
            </div>
          </div>
          <div class="sig-name-line">
            <span style="font-size: 13px; color: var(--text-muted);">${formattedAnrede} ${this.formData.vorname} ${this.formData.nachname}</span>
          </div>
        </div>
      </div>
    `;
  }

  // --- Speichern eines Patienten (Wizard Abschluss) ---

  async submitPatientData() {
    const signatureDataUrl = this.signaturePad ? this.signaturePad.toDataURL() : null;
    const signedPackage = this.contracts.generateSignedSummary(this.formData, signatureDataUrl);

    const formattedAnrede = this.getFormattedAnredeWithTitles();
    const fullSvnr = this.formData.vsnrFull || `${this.formData.vsnrNummer}${this.formData.vsnrGeburtsdatum}`;

    const record = {
      id: 'rec_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
      createdAt: new Date().toISOString(),
      readableDate: new Date().toLocaleDateString('de-AT', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      }),
      patient: {
        anrede: formattedAnrede, // Titel in Anrede (Punkt 4)
        titel: this.getAllTitles().join(' '),
        vorname: this.formData.vorname,
        nachname: this.formData.nachname,
        vsnr: fullSvnr,
        krankenkasse: this.formData.krankenkasse,
        plz: this.formData.plz,
        ort: this.formData.ort,
        strasse: this.formData.strasse,
        hausnummer: this.formData.hausnummer,
        adresszusatz: this.formData.adresszusatz,
        kilometergeld: 0.0,
        is_hausbesuch: false
      },
      contracts: signedPackage,
      signature: signatureDataUrl,
      synced: false,
      syncedAt: null
    };

    // Immer sofort lokal sichern (100% Offline-Sicherheit)
    this.localRecords.push(record);
    this.savePersistedState();
    this.updateDashboardStats();

    // Erfolgsbildschirm anzeigen
    this.renderStep(7);

    let countdown = this.config.autoResetSeconds;
    const timerElem = document.getElementById('resetCountdown');
    if (timerElem) timerElem.textContent = countdown;

    const interval = setInterval(() => {
      countdown--;
      if (timerElem) timerElem.textContent = countdown;
      if (countdown <= 0) {
        clearInterval(interval);
        this.resetForm();
        this.switchView('dashboard');
      }
    }, 1000);

    const resetBtn = document.getElementById('btnNewPatient');
    if (resetBtn) {
      resetBtn.onclick = () => {
        clearInterval(interval);
        this.resetForm();
        this.renderStep(1);
      };
    }

    const dashBtn = document.getElementById('btnSuccessToDash');
    if (dashBtn) {
      dashBtn.onclick = () => {
        clearInterval(interval);
        this.resetForm();
        this.switchView('dashboard');
      };
    }
  }

  resetForm() {
    this.formData = {
      anrede: 'Frau',
      titel: [],
      customTitel: '',
      vorname: '',
      nachname: '',
      vsnrNummer: '',
      vsnrGeburtsdatum: '',
      vsnrFull: '',
      strasse: '',
      hausnummer: '',
      adresszusatz: '',
      plz: '',
      ort: '',
      krankenkasse: ''
    };

    if (this.signaturePad) this.signaturePad.clear();

    document.querySelectorAll('.input-resetable').forEach(input => input.value = '');
    document.querySelectorAll('.consent-checkbox').forEach(cb => cb.checked = false);
    document.querySelectorAll('.title-chip').forEach(c => c.classList.remove('selected'));

    const customTitleBox = document.getElementById('selectedTitlesContainer');
    if (customTitleBox) customTitleBox.innerHTML = '';

    const firstCard = document.querySelector('.choice-card-anrede[data-value="Frau"]');
    if (firstCard) {
      document.querySelectorAll('.choice-card-anrede').forEach(c => c.classList.remove('selected'));
      firstCard.classList.add('selected');
    }

    this.updateSummaryCard();
  }

  // --- Event Listener Registrierung ---

  setupEventListeners() {
    // Dashboard Aktionen (Punkt 1)
    const btnNewPat = document.getElementById('btnDashNewPatient');
    if (btnNewPat) {
      btnNewPat.onclick = () => {
        this.resetForm();
        this.switchView('patient');
        this.renderStep(1);
      };
    }

    const btnScanQr = document.getElementById('btnDashScanQr');
    if (btnScanQr) btnScanQr.onclick = () => this.openQrScanner();

    const btnDashSync = document.getElementById('btnDashSync');
    if (btnDashSync) btnDashSync.onclick = () => this.openSyncReview();

    const btnBackToDash = document.getElementById('btnBackToDashFromWizard');
    if (btnBackToDash) btnBackToDash.onclick = () => this.switchView('dashboard');

    // QR-Scanner Controls
    const btnCloseQr = document.getElementById('btnCloseQrScanner');
    if (btnCloseQr) btnCloseQr.onclick = () => this.closeQrScanner();

    const btnApplyManualQr = document.getElementById('btnApplyManualQr');
    const manualQrInput = document.getElementById('manualQrInput');
    if (btnApplyManualQr && manualQrInput) {
      btnApplyManualQr.onclick = () => {
        this.handleQrScanResult(manualQrInput.value.trim());
      };
    }

    // Pre-Sync Review Controls (Punkt 2 & 3)
    const btnCloseReview = document.getElementById('btnCloseSyncReview');
    if (btnCloseReview) {
      btnCloseReview.onclick = () => {
        const modal = document.getElementById('syncReviewView');
        if (modal) modal.classList.add('hidden');
      };
    }

    const btnConfirmSync = document.getElementById('btnConfirmAndSendSync');
    if (btnConfirmSync) btnConfirmSync.onclick = () => this.executeBatchSync();

    // Wizard Navigation
    const btnNext = document.getElementById('btnStepNext');
    const btnBack = document.getElementById('btnStepBack');
    if (btnNext) btnNext.onclick = () => {
      this.closeKeyboard();
      this.goToNextStep();
    };
    if (btnBack) btnBack.onclick = () => {
      this.closeKeyboard();
      this.goToPrevStep();
    };

    // Anrede & Titel
    document.querySelectorAll('.choice-card-anrede').forEach(card => {
      card.onclick = () => {
        document.querySelectorAll('.choice-card-anrede').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        this.formData.anrede = card.dataset.value;
        this.updateSummaryCard();
        this.validateCurrentStep();
      };
    });

    document.querySelectorAll('.title-chip').forEach(chip => {
      chip.onclick = () => {
        const titleVal = chip.dataset.title;
        if (chip.classList.contains('selected')) {
          chip.classList.remove('selected');
          this.formData.titel = this.formData.titel.filter(t => t !== titleVal);
        } else {
          chip.classList.add('selected');
          this.formData.titel.push(titleVal);
        }
        this.updateSummaryCard();
      };
    });

    const btnCustomTitle = document.getElementById('btnAddCustomTitle');
    const customTitleInput = document.getElementById('inputCustomTitle');
    if (btnCustomTitle && customTitleInput) {
      btnCustomTitle.onclick = () => {
        const val = customTitleInput.value.trim();
        if (val && !this.formData.titel.includes(val)) {
          this.formData.titel.push(val);
          customTitleInput.value = '';
          const container = document.getElementById('selectedTitlesContainer');
          if (container) {
            const span = document.createElement('span');
            span.className = 'title-chip selected';
            span.textContent = val;
            container.appendChild(span);
          }
          this.updateSummaryCard();
        }
      };
    }

    // Eingabefelder Name & Adresse
    const bindInput = (id, field) => {
      const el = document.getElementById(id);
      if (el) {
        el.oninput = (e) => {
          this.formData[field] = e.target.value;
          this.updateSummaryCard();
          this.validateCurrentStep();
        };
      }
    };

    bindInput('inputVorname', 'vorname');
    bindInput('inputNachname', 'nachname');
    bindInput('inputStrasse', 'strasse');
    bindInput('inputHausnummer', 'hausnummer');
    bindInput('inputAdresszusatz', 'adresszusatz');
    bindInput('inputOrt', 'ort');
    const krankenkasseEl = document.getElementById('inputKrankenkasse');
    if (krankenkasseEl) {
      krankenkasseEl.onchange = (event) => {
        this.formData.krankenkasse = event.target.value;
        this.updateSummaryCard();
        this.validateCurrentStep();
      };
    }

    // PLZ mit automatischem Stadtnamen-Lookup
    const plzEl = document.getElementById('inputPlz');
    if (plzEl) {
      plzEl.oninput = (e) => {
        this.formData.plz = e.target.value.trim();
        if (this.formData.plz.length === 4) {
          const autoCity = lookupAustrianCity(this.formData.plz);
          const ortEl = document.getElementById('inputOrt');
          if (autoCity && ortEl && !ortEl.value) {
            ortEl.value = autoCity;
            this.formData.ort = autoCity;
          }
        }
        this.updateSummaryCard();
        this.validateCurrentStep();
      };
    }

    // SVNr Numpad
    this.setupNumpad();

    // Signatur löschen
    const btnClearSig = document.getElementById('btnClearSignature');
    if (btnClearSig) {
      btnClearSig.onclick = () => {
        if (this.signaturePad) {
          this.signaturePad.clear();
          this.updateSignatureBadge();
          this.validateCurrentStep();
        }
      };
    }

    // Absenden
    const btnSubmit = document.getElementById('btnSubmitAll');
    if (btnSubmit) btnSubmit.onclick = () => this.submitPatientData();

    // Admin Navigation
    const btnAdminDash = document.getElementById('btnOpenAdminFromDash');
    if (btnAdminDash) btnAdminDash.onclick = () => this.promptAdminAccess();

    const btnCloseAdmin = document.getElementById('btnCloseAdmin');
    if (btnCloseAdmin) btnCloseAdmin.onclick = () => this.switchView('dashboard');

    this.setupAdminControls();
  }

  // --- SVNr Numpad ---

  setupNumpad() {
    const inputLaufnr = document.getElementById('inputVsnrNummer');
    const inputGebdat = document.getElementById('inputVsnrGeburtsdatum');

    if (inputLaufnr) {
      inputLaufnr.onclick = () => {
        this.activeNumpadTarget = 'vsnrNummer';
        this.highlightActiveNumpad();
      };
    }
    if (inputGebdat) {
      inputGebdat.onclick = () => {
        this.activeNumpadTarget = 'vsnrGeburtsdatum';
        this.highlightActiveNumpad();
      };
    }

    document.querySelectorAll('.numpad-btn').forEach(btn => {
      btn.onclick = () => this.handleNumpadKey(btn.dataset.key);
    });
  }

  highlightActiveNumpad() {
    const inputLaufnr = document.getElementById('inputVsnrNummer');
    const inputGebdat = document.getElementById('inputVsnrGeburtsdatum');
    if (inputLaufnr) inputLaufnr.classList.toggle('active-numpad-field', this.activeNumpadTarget === 'vsnrNummer');
    if (inputGebdat) inputGebdat.classList.toggle('active-numpad-field', this.activeNumpadTarget === 'vsnrGeburtsdatum');
  }

  handleNumpadKey(key) {
    const targetId = (this.activeNumpadTarget === 'vsnrNummer') ? 'inputVsnrNummer' : 'inputVsnrGeburtsdatum';
    const inputElem = document.getElementById(targetId);
    if (!inputElem) return;

    let currentVal = inputElem.value;
    const maxLen = (this.activeNumpadTarget === 'vsnrNummer') ? 4 : 6;

    if (key === 'backspace') {
      inputElem.value = currentVal.slice(0, -1);
    } else if (key === 'clear') {
      inputElem.value = '';
    } else if (/^\d$/.test(key)) {
      if (currentVal.length < maxLen) {
        inputElem.value = currentVal + key;
      }
    }

    // Update formData BEFORE switching targets
    if (this.activeNumpadTarget === 'vsnrNummer') this.formData.vsnrNummer = inputElem.value;
    else this.formData.vsnrGeburtsdatum = inputElem.value;

    // Auto-switch from Laufnummer (4 digits) → Geburtsdatum (6 digits)
    if (this.activeNumpadTarget === 'vsnrNummer' && inputElem.value.length === 4) {
      this.activeNumpadTarget = 'vsnrGeburtsdatum';
      this.highlightActiveNumpad();
    }

    this.validateAustrianSvnr();
  }

  validateAustrianSvnr() {
    const laufnr = this.formData.vsnrNummer || '';
    const gebdat = this.formData.vsnrGeburtsdatum || '';
    const fullSvnr = (laufnr + gebdat).trim();
    this.formData.vsnrFull = fullSvnr;

    const badge = document.getElementById('svnrValidationBadge');

    if (fullSvnr.length < 10) {
      if (badge) {
        badge.className = 'status-badge neutral';
        badge.textContent = `Eingabe: ${fullSvnr.length}/10 Ziffern`;
      }
      this.updateSummaryCard();
      this.validateCurrentStep();
      return false;
    }

    const factors = [3, 7, 9, 0, 5, 8, 4, 2, 1, 6];
    let sum = 0;
    for (let i = 0; i < 10; i++) sum += parseInt(fullSvnr[i], 10) * factors[i];
    const remainder = sum % 11;
    const checkDigit = parseInt(fullSvnr[3], 10);

    const day = parseInt(gebdat.slice(0, 2), 10);
    const month = parseInt(gebdat.slice(2, 4), 10);
    const year = parseInt(gebdat.slice(4, 6), 10);
    const isValidDate = (day >= 1 && day <= 31 && month >= 1 && month <= 12);
    const isValidChecksum = (remainder === checkDigit && remainder !== 10);

    if (isValidChecksum && isValidDate) {
      if (badge) {
        badge.className = 'status-badge success';
        badge.textContent = `Gültig (Geburtsdatum: ${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${year < 30 ? '20' : '19'}${String(year).padStart(2, '0')})`;
      }
      this.updateSummaryCard();
      this.validateCurrentStep();
      return true;
    } else {
      if (badge) {
        badge.className = 'status-badge warning';
        badge.textContent = isValidChecksum ? 'Prüfziffer stimmt, aber Datum unplausibel' : 'Prüfziffer ungültig (Bitte Tippfehler prüfen)';
      }
      this.updateSummaryCard();
      this.validateCurrentStep();
      return false;
    }
  }

  // --- Admin Controls ---

  async promptAdminAccess() {
    const enteredPin = await this.showAppDialog(
      'Admin-Zugang',
      'Bitte Admin-PIN eingeben:',
      { showInput: true, inputType: 'password', variant: 'info' }
    );
    if (enteredPin === this.config.adminPin) {
      this.switchView('admin');
    } else if (enteredPin !== null) {
      await this.showAppDialog('Zugriff verweigert', 'Die eingegebene PIN ist falsch.', { variant: 'error' });
    }
  }

  populateAdminData() {
    const hostInput = document.getElementById('adminHostInput');
    const portInput = document.getElementById('adminPortInput');
    const tokenInput = document.getElementById('adminTokenInput');
    const praxisNameInput = document.getElementById('adminPraxisName');
    const pinInput = document.getElementById('adminPinInput');

    if (hostInput) hostInput.value = this.connection.host;
    if (portInput) portInput.value = this.connection.port;
    if (tokenInput) tokenInput.value = this.connection.token;
    if (praxisNameInput) praxisNameInput.value = this.config.praxisName;
    if (pinInput) pinInput.value = this.config.adminPin;

    this.renderAdminContractsList();
  }

  setupAdminControls() {
    const btnSaveConn = document.getElementById('btnAdminSaveConn');
    if (btnSaveConn) {
      btnSaveConn.onclick = async () => {
        const hostInput = document.getElementById('adminHostInput');
        const portInput = document.getElementById('adminPortInput');
        const tokenInput = document.getElementById('adminTokenInput');

        if (hostInput) this.connection.host = hostInput.value.trim();
        if (portInput) this.connection.port = parseInt(portInput.value.trim(), 10) || 5000;
        if (tokenInput) this.connection.token = tokenInput.value.trim();

        this.savePersistedState();
        this.checkConnection();
        await this.showAppDialog('Gespeichert', 'Die Verbindungseinstellungen wurden gespeichert.', { variant: 'success' });
      };
    }

    const btnTestConn = document.getElementById('btnAdminTestConn');
    if (btnTestConn) {
      btnTestConn.onclick = async () => {
        btnTestConn.disabled = true;
        btnTestConn.textContent = 'Teste...';
        const ok = await this.checkConnection();
        await this.showAppDialog(
          ok ? 'Verbindung erfolgreich' : 'Verbindung nicht möglich',
          ok ? 'Die Verbindung zu LeprendiX wurde hergestellt.' : 'LeprendiX ist derzeit nicht erreichbar.',
          { variant: ok ? 'success' : 'warning' }
        );
        btnTestConn.disabled = false;
        btnTestConn.textContent = 'Verbindung testen';
      };
    }

    const btnSavePraxis = document.getElementById('btnAdminSavePraxis');
    if (btnSavePraxis) {
      btnSavePraxis.onclick = async () => {
        const praxisName = document.getElementById('adminPraxisName');
        const pinInput = document.getElementById('adminPinInput');

        if (praxisName) this.config.praxisName = praxisName.value.trim();
        if (pinInput && pinInput.value.trim()) this.config.adminPin = pinInput.value.trim();

        this.savePersistedState();
        await this.showAppDialog('Gespeichert', 'Die Praxiseinstellungen wurden gespeichert.', { variant: 'success' });
      };
    }
  }

  renderAdminContractsList() {
    const list = document.getElementById('adminContractsList');
    if (!list) return;
    list.innerHTML = '';

    this.contracts.contractsIndex.forEach(c => {
      const row = document.createElement('div');
      row.className = 'admin-contract-row';
      const info = document.createElement('div');
      info.className = 'admin-contract-info';
      const title = document.createElement('strong');
      title.textContent = c.title;
      const filename = document.createElement('span');
      filename.className = 'text-muted';
      filename.textContent = ` (${c.file})`;
      const badge = document.createElement('span');
      badge.className = `badge ${c.required ? 'badge-required' : 'badge-optional'}`;
      badge.textContent = c.required ? 'Pflicht' : 'Optional';
      info.append(title, filename, badge);

      const label = document.createElement('label');
      label.className = 'switch';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = c.enabled;
      checkbox.disabled = c.required;
      const slider = document.createElement('span');
      slider.className = 'slider round';
      label.append(checkbox, slider);
      row.append(info, label);

      checkbox.onchange = (e) => {
        try {
          this.contracts.setContractEnabled(c.id, e.target.checked);
        } catch (error) {
          e.target.checked = c.enabled;
          this.showAppDialog(
            'Vertragseinstellung',
            `Die Auswahl konnte nicht gespeichert werden: ${error.message}`,
            { variant: 'error' }
          );
        }
      };

      list.appendChild(row);
    });
  }
}

// Beim Laden starten
window.addEventListener('DOMContentLoaded', () => {
  window.companionApp = new CompanionApp();
});
