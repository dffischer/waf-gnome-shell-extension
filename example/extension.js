const St = imports.gi.St;
const Mainloop = imports.mainloop;
const Main = imports.ui.main;
const settings = imports.misc.extensionUtils.getCurrentExtension().imports.convenience.getSettings();

function _showHello() {
  let label = new St.Label({ text: settings.get_string('hello-text') || "Hello, world!" });
  let monitor = Main.layoutManager.primaryMonitor;
  global.stage.add_actor(label);
  label.set_position(Math.floor (monitor.width / 2 - label.width / 2), Math.floor(monitor.height / 2 - label.height / 2));
  Mainloop.timeout_add(3000, function () { label.destroy(); });
}

function init() {
}

let signalId;

function enable() {
  Main.panel.actor.reactive = true;
  signalId = Main.panel.actor.connect('button-release-event', _showHello);
}

function disable() {
  if (signalId) {
    Main.panel.actor.disconnect(signalId);
    signalId = 0;
  }
}
