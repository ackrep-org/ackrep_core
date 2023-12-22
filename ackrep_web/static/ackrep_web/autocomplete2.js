let result_list = document.getElementById("autocomplete-result-list");
let query = document.getElementById("query");
let main_input = document.getElementById("main-input");
const info = document.getElementById("result-info");
let query_content = query.value;
let query_cursor_pos = query.selectionStart;

String.prototype.splice = function(start, delCount, newSubStr) {
  return this.slice(0, start) + newSubStr + this.slice(start + Math.abs(delCount));
};

let keysPressed = {};
// on Ctrl + Space, jump to PyIRK search field
query.addEventListener('keydown', (event) => {
  keysPressed[event.key] = true;

  if (keysPressed['Control'] && event.key == ' ') {
    main_input.focus();
    keysPressed['Control'] = false
  }
});

query.addEventListener('keyup', (event) => {
  delete keysPressed[event.key];
});

query.addEventListener('focusout', (event) => {
  query_content = query.value;
  query_cursor_pos = query.selectionStart;
});



// ✅ Move focus to END of input field
main_input.setSelectionRange(main_input.value.length, main_input.value.length);



async function input_callback({ signal } = {}){
  const query = main_input.value;
  console.log("call", query)
  const url = `/search/?q=${main_input.value}`;
  const source = await fetch(url, {signal});
  const res = await source.json();
//     console.log(res.data);
  console.log("res", query)
  result_list.innerHTML = '';
  if (main_input.value.length == 0) {
      console.log(`input empty`);
      return
  }
  if (res.data.length > 0) {
      info.innerHTML = `Displaying <strong>${res.data.length}</strong> results`;
  } else {
      info.innerHTML = `Found <strong>${res.data.length}</strong> matching results for <strong>"${query}"</strong>`;
  }
  result_list.prepend(info);

  if (res.data.length > 0) {
      res.data.forEach(function(item){
//         console.log(`-->${item}`);
          var li = document.createElement("li");
          li.insertAdjacentHTML("beforeend", `${item}`);
          result_list.appendChild(li);
      });
      // this ensures that math is rendered if it is present.
      MathJax.typeset();
  }
}


// https://www.freecodecamp.org/news/javascript-debounce-example/
function debounce(func, timeout = 400){
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => { func.apply(this, args); }, timeout);
  };
}
main_input.addEventListener("input", debounce(() => input_callback()));


// if we reload the page with content in the input, the result should be shown directly
if (main_input.value.length != 0) {
    input_callback();
}

/*

13: Enter
40: ↓
38: ↑
https://www.toptal.com/developers/keycode/for/l
113: F2
27: ESC

*/


// source: https://codepen.io/mehuldesign/pen/eYpbXMg
var liSelected;
var index = -1;

// keyboard shortcuts for input (arrow keys + Enter)
main_input.addEventListener('keydown', function(event) {
  var maxidx = result_list.getElementsByTagName('li').length - 1;

  if (event.which === 40 && maxidx > -1) {
    index++;
    //down
    if (liSelected) {
      liSelected.classList.remove("selected");
      liSelected.classList.remove("copied");
      next = result_list.getElementsByTagName('li')[index];
      if (typeof next !== undefined && index <= maxidx) {

        liSelected = next;
      } else {
        index = 0;
        liSelected = result_list.getElementsByTagName('li')[0];
      }

      console.log(index);
    } else {
      index = 0;

      liSelected = result_list.getElementsByTagName('li')[0];

    }
    // console.log(`liSelected: ${liSelected}`);
    // console.log(`classList: ${liSelected.classList}`);
    liSelected.classList.add("selected");
    // console.log(`classList2: ${liSelected.classList}`);
    result_list.scrollTop= liSelected.offsetTop - 150
  } else if (event.which === 38 && maxidx > -1) {

    //up
    if (liSelected) {
      liSelected.classList.remove("selected");
      liSelected.classList.remove("copied");
      index--;
      console.log(index);
      next = result_list.getElementsByTagName('li')[index];
      if (typeof next !== undefined && index >= 0) {
        liSelected = next;
      } else {
        index = maxidx;
        liSelected = result_list.getElementsByTagName('li')[maxidx];
      }
    } else {
      index = 0;
      liSelected = result_list.getElementsByTagName('li')[maxidx];
    }
    // console.log(`liSelected-: ${liSelected}`);
    // console.log(`classList-: ${liSelected.classList}`);
    liSelected.classList.add("selected");
    // console.log(`classList2-: ${liSelected.classList}`);
    result_list.scrollTop= liSelected.offsetTop - 150
  } else if (event.which === 13 && liSelected ) {
    //
    // Enter
    //
    var text = JSON.parse(document.getElementById(`sparql_text_${index}`).textContent);
    query.value = query_content.splice(query_cursor_pos, 0, text)
    query.focus()
    query.selectionStart = query_cursor_pos + text.length
    query.selectionEnd = query_cursor_pos + text.length
    clearinput()

  } else if (event.which === 27) {
    // ESC
    console.log("ESC");
    clearinput();
    result_list.innerHTML = '';
  }
}, false);


main_input.addEventListener("focusin",function(event) {
    console.log("Focus");
    //console.log(result_list.innerHTML);
    result_list.classList.remove("hidden");
}, false);

main_input.addEventListener("focusout",function(event) {
    console.log("Focusout");
    setTimeout(hide_result_list, 200);

}, false);

function hide_result_list(){
    // if result_list is not focused then hide it
    if (document.activeElement != main_input) {
        result_list.classList.add("hidden");
    }
}


function clearinput(){

    main_input.value="";
};
