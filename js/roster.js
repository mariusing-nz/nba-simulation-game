export function bestPlayer(roster){return[...roster].sort((a,b)=>b.player.overall-a.player.overall)[0]?.player}
