// Hive-Mind web clipper bookmarklet (Block 7).
//
// Install: create a bookmark in Chrome, name it "Clip to Hive-Mind",
// and paste the single javascript: line below as its URL. Clicking
// it on any page opens the clipper with that page's URL, title, and
// selected text prefilled. Nothing is sent anywhere: the clipper
// only builds a capture payload you paste into your MCP client.
//
// The clipper payload format (parsed by Block 3 capture_idea):
//   first line:  URL: <page url>
//   blank line, then the selected text / your note.
// The scrubber runs before anything is stored, as with all captures.
//
// javascript: line (single line, no line breaks when pasted):
//
// javascript:void(window.open('CLIPPER_URL?url='+encodeURIComponent(location.href)+'&title='+encodeURIComponent(document.title)+'&text='+encodeURIComponent(window.getSelection?window.getSelection().toString():''),'_blank'))
//
// Replace CLIPPER_URL with the address where you serve gui/clipper.html,
// e.g. http://localhost:8765/clipper.html when running the GUI server
// (python -m app.gui_server) from the repo root.

(function () {
    var clipperUrl = "http://localhost:8765/clipper.html";
    var params = "?url=" + encodeURIComponent(location.href)
        + "&title=" + encodeURIComponent(document.title)
        + "&text=" + encodeURIComponent(window.getSelection ? window.getSelection().toString() : "");
    window.open(clipperUrl + params, "_blank");
})();
