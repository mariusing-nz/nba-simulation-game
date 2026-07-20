import{average,clamp}from'./utils.js';
import{assignedPosition,validateLineup}from'./lineup.js?v=20260721-two-click-1';

const roleFit={
  PG:player=>average([player.playmaking,player.shooting]),
  SG:player=>average([player.shooting,player.offense]),
  SF:player=>average([player.offense,player.defense]),
  PF:player=>average([player.defense,player.rebounding]),
  C:player=>average([player.rebounding,player.defense])
};

export function calculateTeamRatings(roster){
  const validation=validateLineup(roster);
  if(!validation.valid)throw new Error(validation.errors[0].message);
  const players=roster.map(slot=>slot.player),get=key=>average(players.map(player=>Number(player[key])));
  const rawOffense=get('offense'),rawDefense=get('defense'),shooting=get('shooting'),playmaking=get('playmaking'),rebounding=get('rebounding'),athleticism=get('athleticism'),playerOverall=get('overall');
  const positionalFit=average(roster.map(slot=>roleFit[assignedPosition(slot)](slot.player)));
  if(![rawOffense,rawDefense,shooting,playmaking,rebounding,athleticism,playerOverall,positionalFit].every(Number.isFinite))throw new Error('Invalid player rating.');
  const fitAdjustment=clamp((positionalFit-82)*.08,-1,1),offense=rawOffense+fitAdjustment,defense=rawDefense+fitAdjustment;
  let chemistry=75+4+(playmaking>=84?3:0)+(shooting>=82?3:0)+(defense>=82?3:0)+(rebounding>=82?3:0)+(positionalFit>=84?2:0);
  chemistry-=Math.min(offense,defense,shooting,playmaking,rebounding)<70?6:0;
  chemistry-=players.filter(player=>player.shooting<70).length>=3?4:0;
  chemistry-=players.filter(player=>player.defense<70).length>=3?4:0;
  chemistry=clamp(Math.round(chemistry),60,95);
  const balance=clamp(Math.round(100-(Math.max(offense,defense,shooting,playmaking,rebounding)-Math.min(offense,defense,shooting,playmaking,rebounding))*1.4),60,99),adjustment=(chemistry+balance)/2-75;
  const overall=clamp(Math.round(.28*playerOverall+.2*offense+.18*defense+.1*shooting+.09*playmaking+.06*rebounding+.04*positionalFit+.05*(75+adjustment)),40,99);
  return{overall,offense:Math.round(offense),defense:Math.round(defense),shooting:Math.round(shooting),playmaking:Math.round(playmaking),rebounding:Math.round(rebounding),athleticism:Math.round(athleticism),chemistry,balance,positionalFit:Math.round(positionalFit),pace:Math.round(94+athleticism/12)};
}
