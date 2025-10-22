/**
 * Auth Broadcast Channel Utility
 * 
 * Provides cross-tab communication for authentication events.
 * When one tab logs out, all other tabs are immediately notified
 * and can clean up their state before redirecting to login.
 * 
 * Browser Support: Chrome 54+, Edge 79+, Safari 15.4+, Firefox 38+
 */

const AUTH_CHANNEL_NAME = 'langflow_auth_channel';

export enum AuthBroadcastEventType {
  LOGOUT = 'LOGOUT',
  LOGIN = 'LOGIN',
}

export interface AuthBroadcastMessage {
  type: AuthBroadcastEventType;
  timestamp: number;
  source?: string; // Optional: to identify which tab sent the message
}

class AuthBroadcastChannel {
  private channel: BroadcastChannel | null = null;
  private listeners: Map<AuthBroadcastEventType, Set<() => void>> = new Map();

  constructor() {
    this.initChannel();
  }

  /**
   * Initialize the BroadcastChannel
   * Gracefully handles browsers that don't support BroadcastChannel
   */
  private initChannel(): void {
    if (typeof BroadcastChannel !== 'undefined') {
      try {
        this.channel = new BroadcastChannel(AUTH_CHANNEL_NAME);
        this.channel.onmessage = this.handleMessage.bind(this);
        console.debug('[AuthBroadcast] Channel initialized');
      } catch (error) {
        console.warn('[AuthBroadcast] Failed to initialize BroadcastChannel:', error);
      }
    } else {
      console.warn('[AuthBroadcast] BroadcastChannel not supported in this browser');
    }
  }

  /**
   * Handle incoming messages from other tabs
   */
  private handleMessage(event: MessageEvent<AuthBroadcastMessage>): void {
    const { type, timestamp } = event.data;
    
    console.debug(`[AuthBroadcast] Received message:`, { type, timestamp, age: Date.now() - timestamp });

    // Execute all registered listeners for this event type
    const listeners = this.listeners.get(type);
    if (listeners && listeners.size > 0) {
      listeners.forEach(callback => {
        try {
          callback();
        } catch (error) {
          console.error(`[AuthBroadcast] Error in listener for ${type}:`, error);
        }
      });
    }
  }

  /**
   * Broadcast a logout event to all other tabs
   */
  public broadcastLogout(): void {
    this.broadcast(AuthBroadcastEventType.LOGOUT);
  }

  /**
   * Broadcast a login event to all other tabs
   */
  public broadcastLogin(): void {
    this.broadcast(AuthBroadcastEventType.LOGIN);
  }

  /**
   * Send a message to all other tabs
   */
  private broadcast(type: AuthBroadcastEventType): void {
    if (!this.channel) {
      console.debug('[AuthBroadcast] Channel not available, skipping broadcast');
      return;
    }

    const message: AuthBroadcastMessage = {
      type,
      timestamp: Date.now(),
      source: window.location.pathname,
    };

    try {
      this.channel.postMessage(message);
      console.debug(`[AuthBroadcast] Broadcasted ${type} event`);
    } catch (error) {
      console.error(`[AuthBroadcast] Failed to broadcast ${type}:`, error);
    }
  }

  /**
   * Register a callback for logout events from other tabs
   */
  public onLogout(callback: () => void): () => void {
    return this.on(AuthBroadcastEventType.LOGOUT, callback);
  }

  /**
   * Register a callback for login events from other tabs
   */
  public onLogin(callback: () => void): () => void {
    return this.on(AuthBroadcastEventType.LOGIN, callback);
  }

  /**
   * Register a callback for a specific event type
   * Returns an unsubscribe function
   */
  private on(type: AuthBroadcastEventType, callback: () => void): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }

    const listeners = this.listeners.get(type)!;
    listeners.add(callback);

    console.debug(`[AuthBroadcast] Registered listener for ${type} (total: ${listeners.size})`);

    // Return unsubscribe function
    return () => {
      listeners.delete(callback);
      console.debug(`[AuthBroadcast] Unregistered listener for ${type} (remaining: ${listeners.size})`);
    };
  }

  /**
   * Close the channel and cleanup
   */
  public close(): void {
    if (this.channel) {
      this.channel.close();
      this.channel = null;
      console.debug('[AuthBroadcast] Channel closed');
    }
    this.listeners.clear();
  }

  /**
   * Check if BroadcastChannel is supported
   */
  public isSupported(): boolean {
    return typeof BroadcastChannel !== 'undefined';
  }
}

// Export singleton instance
export const authBroadcast = new AuthBroadcastChannel();
