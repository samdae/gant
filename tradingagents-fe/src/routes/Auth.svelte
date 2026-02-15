<script lang="ts">
  import { setToken } from "../stores/auth";

  let tokenInput = "";
  let error = "";

  const getReturnPath = () => {
    const hash = window.location.hash;
    const queryIndex = hash.indexOf("?");
    if (queryIndex === -1) return "#/";
    const query = hash.slice(queryIndex + 1);
    const params = new URLSearchParams(query);
    const returnTo = params.get("return");
    if (!returnTo) return "#/";
    try {
      const decoded = decodeURIComponent(returnTo);
      return decoded.startsWith("#/") ? decoded : "#/";
    } catch {
      return "#/";
    }
  };

  const save = () => {
    if (!tokenInput.trim()) {
      error = "Please enter a token.";
      return;
    }
    setToken(tokenInput.trim());
    window.location.hash = getReturnPath();
  };

  const cancel = () => {
    window.location.hash = "#/";
  };
</script>

<section class="page" id="page-auth">
  <div class="page-container" style="max-width:420px">
    <div class="card" style="padding:22px">
      <div class="page-header" style="margin-bottom:12px">
        <h2>Admin Access</h2>
      </div>

      <label class="form-label" for="tokenInput">Admin token</label>
      <input id="tokenInput" type="password" class="input" bind:value={tokenInput} />
      {#if error}
        <div class="error-text" style="margin-top:10px">{error}</div>
      {/if}

      <div class="modal-footer" style="justify-content:flex-end;margin-top:16px">
        <button class="btn btn-ghost" on:click={cancel}>Cancel</button>
        <button class="btn btn-primary" on:click={save}>Save</button>
      </div>
    </div>
  </div>
</section>
