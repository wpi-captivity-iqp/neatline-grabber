import re, sys, subprocess, os
import posixpath, shutil, requests

if len(sys.argv) < 2:
    print "no host specified!"
    sys.exit(1)

url = sys.argv[1]

proto, host = re.match(r'(\w+://)?([\w\.]+)', url).groups()

if not proto:
    proto = "http"
    url = "http://" + url

##
## Stage One - Grab the base site
##

subprocess.check_call(["wget", "-mk", url])

show_dir = os.path.join(host, "neatline", "show")

for name in os.listdir(show_dir):
    path = posixpath.join(url, 'neatline', 'fullscreen', name)
    subprocess.check_call(["wget", "-mk", path])

shutil.rmtree(show_dir)
# move fullscreen to show
os.rename(os.path.join(host, "neatline", "fullscreen"), show_dir)

##
## Stage Two - Make the site work
##

url_cache = set()
def wget_resource(url):
    if url not in url_cache:
        url_cache.add(url)
        subprocess.check_call(["wget", "-x", url])

def to_relative(path, root):
    relative = "\/".join([".."] * root.count("/"))
    if not relative:
        relative = "."
    return relative + path

js_escape = url.replace("/","\/")
escaped_url = re.compile(re.escape(js_escape)+r"((?:\\\/|[\w\-\.#])+)")
def replace_urls(page, root):
    def replace(match):
        relative_url = to_relative(match.group(1), root)
        absolute = url + match.group(1).replace('\\','')

        # print replace_text, absolute
        # raw_input("??")
        if "#" not in absolute:
            wget_resource(absolute)
        return relative_url
    page, count = re.subn(escaped_url, replace, page)
    return (page, count != 0)

image = re.compile(r'"openlayers_theme":"((?:\\\/|[\w\-])+)"')
small_images = ["layer-switcher-maximize.png",
    "layer-switcher-minimize.png",
    "blank.gif",
    "slider.png",
    "zoombar.png",
    "marker.png",
    "blank.gif",
    "marker.png",
    "cloud-popup-relative.png",
    "layer-switcher-maximize.png",
    "layer-switcher-minimize.png",
    "north-mini.png",
    "west-mini.png",
    "east-mini.png",
    "south-mini.png",
    "zoom-plus-mini.png",
    "zoom-world-mini.png",
    "zoom-minus-mini.png",
    "north-mini.png",
    "west-mini.png",
    "zoom-world-mini.png",
    "east-mini.png",
    "south-mini.png",
    "zoom-plus-mini.png",
    "zoom-minus-mini.png",
    "zoom-plus-mini.png",
    "zoom-minus-mini.png",
    "zoom-world-mini.png"]
def get_small_images(page, root):
    def replace(match):
        relative_url = to_relative(match.group(1), root)
        absolute = url + match.group(1).replace('\\','')
        # print relative_url, absolute
        # raw_input("??")
        for i in small_images:
            wget_resource(posixpath.join(absolute, i))
        return '"openlayers_theme":"{}"'.format(relative_url)
    page, count = re.subn(image, replace, page)
    return (page, count != 0)

records_api = re.compile(r'"record_api":"((?:\\\/|[\w\-])+)"')
exhibit_id = re.compile(r'"id":(\d+)')
neatline_func = """
Neatline.Shared.Record.Collection.prototype.fetch = function(params) {
  var out = this.set(this.parse(neatline_static_record_data));
  if (out) {
    params.success && params.success(this, neatline_static_record_data);
    this.trigger("sync", this, neatline_static_record_data);
  }
}

Neatline.Shared.Record.Collection.prototype.model.prototype.fetch = function(params) {
  var model = _.find(neatline_static_record_data.records, {id: +this.id})
  var out = this.set(this.parse(model));
  if (out) {
    params.success && params.success(this, model);
    this.trigger("sync", this, model);
  }
}"""

href_re = re.compile(r'(?<=href=\\")(\\\/(?:[-\w#]|\\\/)+)')
def get_records(page, root):
    records_url = re.search(records_api, page)
    eid = re.search(exhibit_id, page)
    if records_url and eid:
        absolute = url + records_url.group(1).replace('\\','')
        param_data = {"exhibit_id": eid.group(1)}

        print "making request", absolute, param_data
        data = requests.get(absolute, params=param_data).text
        data, _ = replace_urls(data, root)
        data = re.sub(r"\\\/fullscreen\\\/", r"\/show\/", data)
        def repl(m):
            return to_relative(m.group(1), root)
        data = re.sub(href_re, repl, data)

        template = "<script>\n  var neatline_static_record_data = {}; {}\n</script>"
        data = template.format(data, neatline_func)
        page = re.sub("</head>", lambda m: data + "\n</head>", page, count = 1)

        return page, True

    return page, False

login_page = re.compile('<h1>Log In</h1>')
for root, dirs, files in os.walk(host):
    for i in files:
        with open(os.path.join(root, i), 'r+') as file:
            page = file.read()

            if re.search(login_page, page):
                file.close()
                os.remove(os.path.join(root, i))
                continue

            page, modified0 = replace_urls(page, root)
            page, modified1 = get_small_images(page, root)
            page, modified2 = get_records(page, root)

            if modified0 or modified1 or modified2:
                file.seek(0)
                file.write(page)
                file.truncate()
