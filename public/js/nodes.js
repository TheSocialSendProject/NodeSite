
ajax_load_block();
ajax_load_conns();

function ajax_load_block() {
  element = "";
  path = "/api/getbestblock";
  var xhr = new XMLHttpRequest();
  xhr.open('GET', path, true);
  xhr.onreadystatechange = function() {
      if (this.readyState !== 4) return;
      if (this.status !== 200) return;
      json = JSON.parse(this.responseText);
      document.getElementById("blockhash").innerHTML = json.blockhash;
      document.getElementById("blockcount").innerHTML = json.height;
  };
  xhr.send();
}

function ajax_load_conns() {
  element = "";
  path = "/api/getconnectioncount";
  var xhr = new XMLHttpRequest();
  xhr.open('GET', path, true);
  xhr.onreadystatechange = function() {
      if (this.readyState !== 4) return;
      if (this.status !== 200) return;
      json = JSON.parse(this.responseText);
      document.getElementById("networkconn").innerHTML = json.connections;
  };
  xhr.send();
}
