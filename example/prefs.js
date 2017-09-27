const GObject = imports.gi.GObject;
const Gio = imports.gi.Gio;
const Gtk = imports.gi.Gtk;
const Me = imports.misc.extensionUtils.getCurrentExtension();
const Convenience = Me.imports.lib.convenience;
const settings = Convenience.getSettings();

function init() {
}

const ExamplePrefsWidget = new GObject.Class({
  Name: 'Example.Prefs.Widget',
  GTypeName: 'ExamplePrefsWidget',
  Extends: Gtk.Grid,

  _init: function(params) {
    this.parent(params);
    this.margin = 12;
    this.row_spacing = this.column_spacing = 6;
    this.set_orientation(Gtk.Orientation.VERTICAL);

    this.add(new Gtk.Label({ label: '<b>' + "Message" + '</b>',
      use_markup: true, halign: Gtk.Align.START }));
    let entry = new Gtk.Entry({ hexpand: true, margin_bottom: 12 });
    this.add(entry);
    settings.bind('hello-text', entry, 'text', Gio.SettingsBindFlags.DEFAULT);
  }
});

function buildPrefsWidget() {
  let widget = new ExamplePrefsWidget();
  widget.show_all();
  return widget;
}
