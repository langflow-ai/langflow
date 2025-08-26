#!/usr/bin/env node

/**
 * 🧞 Genie Statusline Wrapper
 * Cross-platform statusline orchestrator that works on Windows, Mac, and Linux
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Get stdin data
let stdinData = '';
process.stdin.setEncoding('utf8');

process.stdin.on('data', (chunk) => {
  stdinData += chunk;
});

process.stdin.on('end', async () => {
  const projectRoot = path.dirname(__dirname);
  const localStatusline = path.join(projectRoot, 'lib', 'statusline.js');
  
  // Array to collect all outputs
  const outputs = [];
  
  try {
    // Check if we're running from local development
    if (fs.existsSync(localStatusline)) {
      // Local development - use local file
      const result = await runCommand('node', [localStatusline], stdinData);
      if (result) outputs.push(result);
    } else {
      // Installed via npm - use npx
      const result = await runCommand('npx', ['-y', 'automagik-genie', 'statusline'], stdinData);
      if (result) outputs.push(result);
    }
    
    // Only run automagik-genie statusline - no external tools
    
  } catch (error) {
    outputs.push('🧞 Genie statusline error: ' + error.message);
  }
  
  // Output all results with newline separation
  console.log(outputs.join('\n'));
});

/**
 * Run a command with stdin data and return stdout
 */
function runCommand(command, args, input) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      shell: process.platform === 'win32', // Use shell on Windows for npx
      windowsHide: true, // Hide console window on Windows
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    let stdout = '';
    let stderr = '';
    
    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    child.on('error', (error) => {
      // Command not found or other spawn errors
      reject(error);
    });
    
    child.on('close', (code) => {
      if (code === 0) {
        resolve(stdout.trim());
      } else {
        // Non-zero exit code, but we might still have output
        if (stdout.trim()) {
          resolve(stdout.trim());
        } else {
          reject(new Error(stderr || `Command failed with code ${code}`));
        }
      }
    });
    
    // Send input data
    if (input) {
      child.stdin.write(input);
      child.stdin.end();
    }
  });
}