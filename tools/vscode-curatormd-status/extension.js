const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFile } = require('child_process');

const COLORS = {
  green: '#73d216',
  blue: '#4da6ff',
  purple: '#c061cb',
  yellow: '#fce94f',
  cyan: '#34e2e2',
  red: '#ef2929',
  gray: '#888888',
};

function workspaceRoot() {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function check(root, profile) {
  return new Promise((resolve) => {
    const script = path.join(__dirname, 'health-check.py');
    execFile('python3', [script, '--project-root', root, '--profile', profile], {
      cwd: root,
      timeout: 15000,
      maxBuffer: 1024 * 1024,
    }, (error, stdout) => {
      if (error) {
        resolve({
          state: 'unknown',
          color: 'gray',
          label: 'UNAVAILABLE',
          failures: ['status checker'],
          error: error.message,
        });
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (parseError) {
        resolve({
          state: 'unknown',
          color: 'gray',
          label: 'UNAVAILABLE',
          failures: ['status checker'],
          error: parseError.message,
        });
      }
    });
  });
}

function runCurator(root, profile, command, extraArgs = []) {
  return new Promise((resolve, reject) => {
    const candidates = [path.join(root, 'plugins', 'curatormd', 'scripts', 'curatormd.py')];
    if (process.env.CURATORMD_SOURCE_DIR) candidates.push(path.join(process.env.CURATORMD_SOURCE_DIR, 'curatormd.py'));
    const profileConfig = path.join(os.homedir(), '.hermes', 'profiles', profile, 'config.yaml');
    try {
      const config = fs.readFileSync(profileConfig, 'utf8');
      const serverScript = config.match(/^\s*-\s+([^\n]*curatormd\/scripts\/mcp_server\.py)\s*$/m)?.[1];
      if (serverScript) candidates.push(path.join(path.dirname(serverScript), 'curatormd.py'));
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    const codexPlugins = path.join(os.homedir(), '.codex', 'plugins', 'cache', 'personal', 'curatormd');
    if (fs.existsSync(codexPlugins)) {
      for (const version of fs.readdirSync(codexPlugins).sort().reverse()) {
        candidates.push(path.join(codexPlugins, version, 'scripts', 'curatormd.py'));
      }
    }
    candidates.push(path.join(os.homedir(), '.hermes', 'plugins', 'curatormd', 'scripts', 'curatormd.py'));
    const script = candidates.find((candidate) => fs.existsSync(candidate));
    if (!script) {
      reject(new Error('CuratorMD runtime was not found in this workspace or the installed plugin paths.'));
      return;
    }
    execFile('python3', [script, '--project-root', root, '--profile', profile, command, ...extraArgs], {
      cwd: root,
      timeout: 30000,
      maxBuffer: 2 * 1024 * 1024,
    }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error((stderr || error.message).trim()));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (parseError) {
        reject(parseError);
      }
    });
  });
}

function markdownText(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function quoteMarkdown(value) {
  const normalized = String(value ?? '').trim();
  return normalized ? normalized.split(/\r?\n/).map((line) => `> ${markdownText(line)}`).join('\n') : '> _Unavailable._';
}

function decisionMarkers(recordId) {
  return {
    start: `<!-- curatormd-decision:${recordId}:start -->`,
    end: `<!-- curatormd-decision:${recordId}:end -->`,
  };
}

function fencedJson(value) {
  const json = JSON.stringify(value, null, 2);
  let fence = '```';
  while (json.includes(fence)) fence += '`';
  return `${fence}json\n${json}\n${fence}`;
}

function previousDecision(documentText, recordId) {
  const markers = decisionMarkers(recordId);
  const start = documentText.indexOf(markers.start);
  if (start < 0) return null;
  const bodyStart = start + markers.start.length;
  const end = documentText.indexOf(markers.end, bodyStart);
  if (end < 0) return null;
  const body = documentText.slice(bodyStart, end);
  const match = body.match(/(`{3,})json[ \t]*\r?\n([\s\S]*?)\r?\n\1/);
  if (!match) return null;
  try {
    const value = JSON.parse(match[2]);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch (_) {
    return null;
  }
}

function decisionValues(record, previousText) {
  const candidate = record.candidate || {};
  const proposal = record.proposal || {};
  const values = {
    priority: Number.isInteger(proposal.priority) ? proposal.priority : 0,
    archive: ['agents', 'sop', 'history', 'lessons'].includes(proposal.archive)
      ? proposal.archive
      : (['agents', 'sop', 'history', 'lessons'].includes(candidate.kind) ? candidate.kind : 'history'),
    title: String(candidate.title || ''),
    content: String(candidate.content || ''),
    utility: String(candidate.utility || ''),
    impact: String(candidate.impact || ''),
  };
  const old = previousDecision(previousText, record.record_id);
  if (!old) return values;
  if (Number.isInteger(old.priority) && old.priority >= 0 && old.priority <= 5) values.priority = old.priority;
  if (['agents', 'sop', 'history', 'lessons'].includes(old.archive)) values.archive = old.archive;
  for (const key of ['title', 'content', 'utility', 'impact']) {
    if (typeof old[key] === 'string') values[key] = old[key];
  }
  return values;
}

function reviewDocument(records, previousText = '') {
  const lines = [
    '# CuratorMD review queue',
    '',
    '> Each record has three parallel parts: (1) concise metadata and safe payload JSON, (2) CuratorMD’s AI proposal, and (3) your editable decision copy.',
    '> The decision block repeats the AI proposal on purpose: edit your copy while keeping the original recommendation visible for comparison.',
    '> Edit the JSON in “Your decision” before choosing an action. `Approve…` uses those values and the selected archive; `Do not record…` records a rejection. The AI proposal is advisory and remains unchanged.',
    '> `utility` describes what future work can reuse from the event. `impact` describes the evidenced or explicitly expected effect on project quality. Use concrete decisions, repair paths, constraints, verification, and outcomes; these fields do not describe review status.',
    '> Approval appends your edited title and content to the chosen persistence archive; rejection does not write canonical knowledge.',
    '',
    '---',
    '',
  ];
  for (const [index, record] of records.entries()) {
    if (index > 0) lines.push('---', '');
    const id = markdownText(record.record_id);
    const candidate = record.candidate;
    const proposal = record.proposal || {};
    const features = proposal.features || {};
    const summary = record.review_safe_summary?.text || '';
    lines.push(`## ${id}`, '', `<!-- curatormd-record:${id} -->`, '');
    const evidence = {
      meta: {
        event: record.event_type || 'unknown',
        captured_at: record.captured_at || 'unknown',
        queue_status: record.status || 'pending',
      },
      concise_safe_payload: {
        profile: features.profile || null,
        platform: features.platform || null,
        model: features.model || null,
        summary,
        event_payload: record.concise_payload || null,
      },
    };
    lines.push('### 1. Metadata + concise safe payload', '', fencedJson(evidence), '');
    if (candidate) {
      const aiProposal = {
        disposition: proposal.disposition || 'pending',
        approval_probability_percent: typeof proposal.disposition_probability === 'number'
          ? Number((proposal.disposition_probability * 100).toFixed(1))
          : null,
        priority: proposal.priority ?? null,
        priority_probability_percent: typeof proposal.priority_probabilities?.[String(proposal.priority)] === 'number'
          ? Number((proposal.priority_probabilities[String(proposal.priority)] * 100).toFixed(1))
          : null,
        archive: proposal.archive || candidate.kind || null,
        archive_probability_percent: typeof proposal.archive_probabilities?.[proposal.archive || candidate.kind] === 'number'
          ? Number((proposal.archive_probabilities[proposal.archive || candidate.kind] * 100).toFixed(1))
          : null,
        title: candidate.title || '',
        content: candidate.content || '',
        utility: candidate.utility || '',
        impact: candidate.impact || '',
      };
      const decision = decisionValues(record, previousText);
      lines.push('### 2. AI proposal (advisory)', '', fencedJson(aiProposal), '');
      lines.push('### 3. Your decision (edit this copy)', '');
      lines.push('Edit the JSON values below. The button you click sets disposition; priority, archive, title, and content come from this copy, not the AI block.', '');
      lines.push(`<!-- curatormd-actions:${id} -->`);
      const markers = decisionMarkers(id);
      lines.push(markers.start, fencedJson(decision), markers.end, '');
    } else {
      lines.push('### 2. AI proposal', '', 'Not ready: there is no safe candidate for review.', '');
      lines.push('### 3. Your decision', '', 'No decision block or action is available until CuratorMD generates a safe candidate.', '');
    }
  }
  if (!records.length) lines.push('There are no pending CuratorMD review notes.');
  return `${lines.join('\n')}\n`;
}

async function reviewRecord(recordId, disposition, root, profile, refresh, openQueue) {
  const reviewPath = path.join(root, '.curatormd', 'reviews', 'pending-review.md');
  const document = vscode.workspace.textDocuments.find((item) => item.uri.fsPath === reviewPath);
  let documentText;
  try {
    documentText = document ? document.getText() : await fs.promises.readFile(reviewPath, 'utf8');
  } catch (error) {
    vscode.window.showErrorMessage(`CuratorMD decision block could not be read: ${error.message}`);
    return;
  }
  const decision = previousDecision(documentText, recordId);
  if (!decision) {
    vscode.window.showErrorMessage(`CuratorMD decision JSON for ${recordId} is missing or invalid.`);
    return;
  }
  if (!Number.isInteger(decision.priority) || decision.priority < 0 || decision.priority > 5) {
    vscode.window.showErrorMessage('Set priority to an integer from 0 through 5 in “Your decision”.');
    return;
  }
  if (disposition === 'approved' && !['agents', 'sop', 'history', 'lessons'].includes(decision.archive)) {
    vscode.window.showErrorMessage('Set archive to agents, sop, history, or lessons in “Your decision”.');
    return;
  }
  for (const key of ['title', 'content', 'utility', 'impact']) {
    if (typeof decision[key] !== 'string') {
      vscode.window.showErrorMessage(`Set ${key} to a string in “Your decision”.`);
      return;
    }
  }
  if (disposition === 'approved' && (!decision.title.trim() || !decision.content.trim())) {
    vscode.window.showErrorMessage('An approved decision needs a non-empty title and content.');
    return;
  }
  if (document?.isDirty && !await document.save()) return;
  const priority = decision.priority;
  if (priority === 5) {
    const confirmed = await vscode.window.showWarningMessage(
      'Priority 5 marks this as the highest-importance CuratorMD entry.',
      { modal: true },
      'Confirm priority 5',
    );
    if (!confirmed) return;
  }
  const edits = {
    title: decision.title,
    content: decision.content,
    utility: decision.utility,
    impact: decision.impact,
  };
  const args = ['--priority', String(priority), '--edits-json', JSON.stringify(edits)];
  if (disposition === 'approved') {
    args.push('--archive', decision.archive);
  }
  try {
    const result = await runCurator(root, profile, 'review', [recordId, disposition, ...args]);
    if (result.error) throw new Error(result.error);
    await vscode.window.showInformationMessage(
      disposition === 'approved' ? `CuratorMD approved and recorded ${recordId}.` : `CuratorMD marked ${recordId} as do not record.`,
    );
    await refresh();
    await openQueue(false);
  } catch (error) {
    vscode.window.showErrorMessage(`CuratorMD review failed: ${error.message}`);
  }
}

function activate(context) {
  const led = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  context.subscriptions.push(led);

  let lastStatus;
  let notifiedPending = 0;
  let activeRoot;
  let activeProfile;
  let refreshing = false;
  let refreshQueued = false;
  let refreshWaiters = [];
  let pollIntervalSeconds = 30;
  const refresh = async () => {
    if (refreshing) {
      refreshQueued = true;
      await new Promise((resolve) => refreshWaiters.push(resolve));
      return;
    }
    refreshing = true;
    try {
    const root = workspaceRoot();
    activeRoot = root;
    if (!root) {
      led.text = '$(circle-slash) CuratorMD: NO WORKSPACE';
      led.color = COLORS.gray;
      led.tooltip = 'Open the CuratorMD workspace to inspect CuratorMD.';
      led.command = 'curatormdStatus.showDetails';
      led.show();
      return;
    }
    const profile = vscode.workspace.getConfiguration('curatormdStatus').get('profile', '');
    if (!profile) {
      lastStatus = { state: 'unknown', color: 'yellow', label: 'PROFILE NOT SET', pendingReview: 0 };
      led.text = '$(circle-question) CuratorMD: PROFILE NOT SET';
      led.color = COLORS.yellow;
      led.tooltip = 'Set curatormdStatus.profile in this workspace’s .vscode/settings.json.';
      led.command = 'curatormdStatus.showDetails';
      led.show();
      return;
    }
    activeProfile = profile;
    lastStatus = await check(root, profile);
    const checkedAt = new Date();
    led.text = `$(circle-filled) CuratorMD: ${lastStatus.label}`;
    led.color = COLORS[lastStatus.color] || COLORS.gray;
    led.tooltip = `${lastStatus.tooltip || 'Click for CuratorMD status details.'}\nLast checked: ${checkedAt.toLocaleTimeString()}\nNext check in: ${pollIntervalSeconds}s`;
    led.command = lastStatus.pendingReview > 0 ? 'curatormdStatus.openReviews' : 'curatormdStatus.showDetails';
    led.show();
    if (lastStatus.pendingReview > 0 && lastStatus.pendingReview !== notifiedPending) {
      notifiedPending = lastStatus.pendingReview;
      void vscode.window.showInformationMessage(
        `CuratorMD has ${lastStatus.pendingReview} notes waiting for review.`,
        'Open Review Notes',
      ).then((action) => {
        if (action === 'Open Review Notes') return openReviewQueue(true);
        return undefined;
      }).catch((error) => {
        vscode.window.showErrorMessage(`Could not open CuratorMD review notes: ${error.message}`);
      });
    } else if (lastStatus.pendingReview === 0) {
      notifiedPending = 0;
    }
    } finally {
      refreshing = false;
      if (refreshQueued) {
        refreshQueued = false;
        try {
          await refresh();
        } finally {
          const waiters = refreshWaiters;
          refreshWaiters = [];
          for (const resolve of waiters) resolve();
        }
      } else {
        const waiters = refreshWaiters;
        refreshWaiters = [];
        for (const resolve of waiters) resolve();
      }
    }
  };

  const openReviewQueue = async (prepare = true) => {
    const root = activeRoot || workspaceRoot();
    const profile = activeProfile || vscode.workspace.getConfiguration('curatormdStatus').get('profile', '');
    if (!root) {
      vscode.window.showInformationMessage('Open a project workspace before reviewing CuratorMD notes.');
      return;
    }
    try {
      if (prepare) await runCurator(root, profile, 'curate');
      const result = await runCurator(root, profile, 'pending-reviews', ['--limit', '100']);
      const records = Array.isArray(result.records) ? result.records : [];
      const reviewDirectory = path.join(root, '.curatormd', 'reviews');
      const reviewPath = path.join(reviewDirectory, 'pending-review.md');
      const reviewUri = vscode.Uri.file(reviewPath);
      await fs.promises.mkdir(reviewDirectory, { recursive: true, mode: 0o700 });
      await fs.promises.chmod(reviewDirectory, 0o700);
      let document = vscode.workspace.textDocuments.find((item) => item.uri.fsPath === reviewPath);
      if (document?.isDirty) {
        vscode.window.showWarningMessage('Save or close the edited CuratorMD review document before refreshing it.');
        return;
      }
      let previousText = document?.getText() || '';
      if (!document) {
        try { previousText = await fs.promises.readFile(reviewPath, 'utf8'); }
        catch (error) { if (error.code !== 'ENOENT') throw error; }
      }
      const content = reviewDocument(records, previousText);
      if (document) {
        const edit = new vscode.WorkspaceEdit();
        edit.replace(document.uri, new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)), content);
        if (!await vscode.workspace.applyEdit(edit) || !await document.save()) {
          throw new Error('The review document could not be refreshed.');
        }
      } else {
        await fs.promises.writeFile(reviewPath, content, { mode: 0o600 });
        document = await vscode.workspace.openTextDocument(reviewUri);
      }
      await vscode.window.showTextDocument(document, { preview: false });
      await refresh();
      if (!records.length) vscode.window.showInformationMessage('There are no pending CuratorMD review notes.');
    } catch (error) {
      vscode.window.showErrorMessage(`Could not open CuratorMD review notes: ${error.message}`);
    }
  };

  const showDetails = async () => {
    if (!lastStatus) {
      vscode.window.showInformationMessage('CuratorMD status is still being checked.');
      return;
    }
    const details = [
      `CuratorMD: ${lastStatus.label}`,
      `Hermes: ${lastStatus.hermes ? 'healthy' : 'unhealthy'}`,
      `Codex: ${lastStatus.codex ? 'healthy' : 'unhealthy'}`,
      `CuratorMD: ${lastStatus.curator ? 'healthy' : 'unhealthy'}`,
      `Capture: ${lastStatus.capture || 'unknown'}`,
      `Review notes: ${lastStatus.pendingReview}`,
      lastStatus.working ? 'CuratorMD is currently working.' : 'CuratorMD is idle.',
    ];
    if (lastStatus.failures?.length) details.push(`Failures: ${lastStatus.failures.join(', ')}`);
    const actions = lastStatus.pendingReview > 0 ? ['Open Review Notes'] : [];
    const action = await vscode.window.showInformationMessage(details.join(' | '), ...actions);
    if (action === 'Open Review Notes') await openReviewQueue(true);
  };

  context.subscriptions.push(vscode.commands.registerCommand('curatormdStatus.refresh', refresh));
  context.subscriptions.push(vscode.commands.registerCommand('curatormdStatus.showDetails', showDetails));
  context.subscriptions.push(vscode.commands.registerCommand('curatormdStatus.openReviews', () => openReviewQueue(true)));
  context.subscriptions.push(vscode.commands.registerCommand('curatormdStatus.reviewRecord', (recordId, disposition) => {
    if (!activeRoot || !activeProfile) return;
    return reviewRecord(recordId, disposition, activeRoot, activeProfile, refresh, openReviewQueue);
  }));
  context.subscriptions.push(vscode.languages.registerCodeLensProvider({ language: 'markdown', scheme: 'file' }, {
    provideCodeLenses(document) {
      if (!document.uri.fsPath.endsWith(path.join('.curatormd', 'reviews', 'pending-review.md'))) return [];
      const lenses = [];
      for (let line = 0; line < document.lineCount; line += 1) {
        const match = document.lineAt(line).text.match(/^<!-- curatormd-actions:([A-Za-z0-9_.-]+) -->$/);
        if (!match) continue;
        const range = new vscode.Range(line, 0, line, document.lineAt(line).text.length);
        lenses.push(new vscode.CodeLens(range, {
          title: '$(check) Approve…',
          command: 'curatormdStatus.reviewRecord',
          arguments: [match[1], 'approved'],
        }));
        lenses.push(new vscode.CodeLens(range, {
          title: '$(circle-slash) Do not record…',
          command: 'curatormdStatus.reviewRecord',
          arguments: [match[1], 'do-not-record'],
        }));
      }
      return lenses;
    },
  }));

  let timer;
  const configurePolling = () => {
    if (timer) clearInterval(timer);
    const configured = Number(vscode.workspace.getConfiguration('curatormdStatus').get('pollSeconds', 30));
    pollIntervalSeconds = Number.isFinite(configured) ? Math.max(5, configured) : 30;
    timer = setInterval(() => void refresh(), pollIntervalSeconds * 1000);
  };
  configurePolling();
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
    if (!event.affectsConfiguration('curatormdStatus')) return;
    configurePolling();
    void refresh();
  }));
  context.subscriptions.push({ dispose: () => clearInterval(timer) });
  refresh();
}

function deactivate() {}

module.exports = { activate, deactivate };
