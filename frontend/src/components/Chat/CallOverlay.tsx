import { useEffect } from 'react';
import { JarvisVoiceScreen } from './JarvisVoiceScreen';
import { useCallStore } from '../../lib/call';
import { useAppStore } from '../../lib/store';

/**
 * Mounted once at the app root. In HUD mode (the default home experience)
 * this is permanently visible and covers the whole app, sidebar included —
 * "no chat, no distractions". If the user switches to classic text mode, it
 * only reappears as a full-screen takeover while a call is actually active,
 * same as before.
 */
/** Connect on its own when the app opens (no "tap core"). Turn off with localStorage jarvis.autoConnect = 'false'. */
function autoConnectEnabled(): boolean {
  try {
    return localStorage.getItem('jarvis.autoConnect') !== 'false';
  } catch {
    return true;
  }
}

export function CallOverlay() {
  const voiceHudMode = useAppStore((s) => s.settings.voiceHudMode);
  const isActive = useCallStore((s) => s.isActive);

  // Runs once per app open. If the user hangs up afterwards it stays hung up. The call hook
  // registers its controls in an effect elsewhere, so retry briefly until the call is active.
  useEffect(() => {
    if (!voiceHudMode || !autoConnectEnabled()) return;
    let tries = 0;
    const timer = window.setInterval(() => {
      const call = useCallStore.getState();
      if (call.isActive || call.error || ++tries > 10) {
        window.clearInterval(timer);
        return;
      }
      call.controls.start();
    }, 700);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!voiceHudMode && !isActive) return null;
  return <JarvisVoiceScreen fullViewport showExitToText={voiceHudMode} />;
}
