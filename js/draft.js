export function eligiblePlayers(data,{teamId,era,position,roster=[],allDrafted=[],strictUniqueness=false}){const candidates=data.playersByTeamEraPosition.get(`${teamId}|${era}|${position}`)||[];const local=new Set(roster.map(slot=>slot.player.id));const global=new Set(allDrafted.map(slot=>slot.player.id));return candidates.filter(player=>player.active&&!local.has(player.id)&&(!strictUniqueness||!global.has(player.id)))}
export function isRosterComplete(roster){return['PG','SG','SF','PF','C'].every(position=>roster.some(slot=>(slot.assignedPosition||slot.position)===position))&&roster.length===5}
export const openLineupPositions=roster=>['PG','SG','SF','PF','C'].filter(position=>!roster.some(slot=>(slot.assignedPosition||slot.position)===position));
export const eligibleOpenPositions=(player,roster)=>openLineupPositions(roster).filter(position=>player.positions.includes(position));
export function filterAndSortPlayers(players,{query='',position='ALL',sort='overall'}={}){const normalized=query.trim().toLowerCase();return players.filter(player=>(!normalized||player.name.toLowerCase().includes(normalized))&&(position==='ALL'||player.positions.includes(position))).sort((a,b)=>sort==='name'?a.name.localeCompare(b.name):b.overall-a.overall||a.name.localeCompare(b.name))}

export const ERA_OPTIONS=[
  {id:'all-time',name:'All-Time'},
  {id:'current',name:'Current'},
  {id:'70s',name:"70's",start:1970,end:1979},
  {id:'80s',name:"80's",start:1980,end:1989},
  {id:'90s',name:"90's",start:1990,end:1999},
  {id:'00s',name:"00's",start:2000,end:2009},
  {id:'10s',name:"10's",start:2010,end:2019}
];

export function eligiblePlayersForEra(data,{teamId,eraId,roster=[],allDrafted=[],strictUniqueness=false}){
  const local=new Set(roster.map(slot=>slot.player.id)),global=new Set(allDrafted.map(slot=>slot.player.id));
  const era=ERA_OPTIONS.find(item=>item.id===eraId);
  return data.players.filter(player=>{
    if(!player.active||player.teamId!==teamId||local.has(player.id)||(strictUniqueness&&global.has(player.id)))return false;
    if(eraId==='current')return player.era==='current';
    if(eraId==='all-time')return player.era==='all-time';
    const year=Number.parseInt(player.season,10);
    return player.era==='all-time'&&(player.decadeTags?.includes(eraId)||(year>=era.start&&year<=era.end));
  }).sort((a,b)=>b.overall-a.overall||a.name.localeCompare(b.name));
}

export function availableEraOptions(data,options){
  return ERA_OPTIONS.filter(era=>eligiblePlayersForEra(data,{...options,eraId:era.id}).some(player=>eligibleOpenPositions(player,options.roster||[]).length))
}
